# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import datetime
import traceback
import re
import json


class Edmunds():

    def __init__(self):
        self.makers = ["Honda", "Toyota", "Mercedes-Benz"]
        self.base_url = "https://www.edmunds.com/"
        self.header = {'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36','Accept-Encoding': 'gzip, deflate, br','Accept-Language': 'en-US,en;q=0.9,hi;q=0.8'}
        self.is_expert = True
        self.res_path = "../../data/Edmunds"
        self.attributes = ["Driving", "Comfort", "Interior", "Utility", "Technology"]

    def get_crawl_list(self):
        crawl_lists = dict()
        for maker in self.makers:
            page = requests.get(self.base_url + maker, headers=self.header)
            time.sleep(3)
            page_soup = BeautifulSoup(page.content, 'lxml')
            models = [info['href'].split('/')[2] for info in page_soup.find_all('a', {'data-tracking-id': "view_content_models"})]
            make = dict()
            for model in list(set(models)):
                print("{} : {} 연도 확인 중".format(maker, model))
                page = requests.get(self.base_url + maker + "/" + model, headers=self.header)
                time.sleep(2)
                page_soup = BeautifulSoup(page.content, 'lxml')
                years = [element.getText() for element in page_soup.find('div', class_="other-years").find_all('a', class_="year year-link")] if page_soup.find('div', class_="other-years") else re.findall("\d+", page_soup.find('h1').getText())
                make.update({model: sorted(list(set(years)))})
            crawl_lists.update({maker: make})

        return crawl_lists

    def get_nav_links(self, url):
        page = requests.get(url, headers=self.header)
        page_soup = BeautifulSoup(page.content, "lxml")
        nav_links = page_soup.find('div', class_='pagination-component')
        if nav_links is not None:
            nav_links = nav_links.find_all('a', class_="px-0_25")
            base = "/".join(nav_links[0]["href"].split("/")[1:-2])
            print("base:", base)
            all_links = [nav_link['href'] for nav_link in nav_links]
            max_page = max([int(link.split('/')[-1].split('=')[-1]) for link in all_links])
            links = [base + "/?pagenum=" + str(value) for value in range(2, max_page + 1)]
            links.append(base)
            links.insert(0, links.pop())
            return links
        else:
            return [url.replace(self.base_url, "")]

    def response_tests(self, lists):
        connection_status = []
        links = []
        urls = []
        start = time.time()
        for maker in self.makers:
            for model in lists[maker].keys():
                for year in lists[maker][model]:
                    sub_base_url = maker.lower() + '/' + model + '/' + year
                    sub_url = sub_base_url + '/review/' if self.is_expert else sub_base_url + '/consumer-reviews/'
                    links.append(sub_url)
                    page = requests.get(self.base_url+sub_url, headers=self.header)
                    connection_status.append(page.status_code)
                    if page.status_code == 200:
                        urls.append(self.base_url+sub_url)
                    else:
                        print("Unable to load webpage: {} Status Code: {}".format(self.base_url + sub_url, page.status_code))
                        continue
        end = time.time()
        runtime = end - start

        print('Runtime: {}'.format(str(datetime.timedelta(seconds=round(runtime)))))

        responses = pd.DataFrame({'address': links, 'status': connection_status})
        responses.to_excel('HTTP_Testing.xlsx', sheet_name='Responses', index=False)

        return urls, print("Connected. HTTP Responses saved as 'HTTP_Testing.xlsx'")

    def get_main_info(self, page_soup):

        img = page_soup.find("img", class_="w-100").attrs['src'] if page_soup.find("img", class_="w-100") else ""
        what_new = [words.getText() for words in page_soup.find("div", class_="editorial-review-whats-new").select('li span')] if page_soup.find("editorial-review-whats-new") else ""
        if page_soup.find("div", id="we-recommend-section") is not None:
            why_recommend = page_soup.find("div", id="we-recommend-section").find("div", class_="size-16")
            why_recommend = why_recommend.getText() if why_recommend else page_soup.find("div", id="we-recommend-section").getText()
        else:
            why_recommend = ""

        if page_soup.find("div", class_="truncated-content") is not None:
            overall_review = "\n".join([p.text for p in page_soup.find("div", class_="truncated-content").find_all("p")])
            overall_score = page_soup.find("div", class_="truncated-content").find("span").getText() if page_soup.find("div", class_="truncated-content").find("span") is not None else "Not scored"
        else:
            overall_review = "Not evaluated"
            overall_score = "Not scored"

        return {
            "img": img,
            "whatsnew": what_new,
            "whyrecommend": why_recommend,
            "overall-review": overall_review,
            "overall-score": overall_score
        }

    def get_feature(self, page_soup):
        feature = dict()
        if page_soup.find("table", {"aria-labelledby": "Overview-section-title"}):
            price = page_soup.find("table", {"aria-labelledby": "Overview-section-title"}).find("div", class_="heading-3").getText()
        else:
            price = ""

        for div in page_soup.find_all("div", "features-section"):
            t_bodies = div.find_all("tbody")
            for tbody in t_bodies:
                for tr in tbody.find_all("tr"):
                    key = tr.find("th").getText() if tr else ""
                    value = tr.find("td").getText() if tr else ""
                    feature.update({key: value})

        return feature, price

    def get_expert_review(self, page_soup):

        try:
            scorecard_ = page_soup.find('div', class_='scorecard')
            if scorecard_ is not None:
                scorecard = scorecard_.select("tr")
                if "" in [list(score.children)[1].text for score in scorecard]:
                    scorecard_dict = dict(map(lambda x: x, [tuple(pair.getText() for pair in list(score.children)) for score in scorecard]))
                else:
                    scorecard_dict = dict(map(lambda rating: (list(rating.children)[0].get_text().lower(), float(list(rating.children)[1].get_text()[:3])), scorecard))
            else:
                scorecard_ = page_soup.find('table', class_='rating-scorecard')
                if scorecard_ is not None: # 2020년
                    scorecard = scorecard_.find_all("th")
                    contents = scorecard_.find_all("td")
                    expert = []
                    for score, content in zip(scorecard, contents):
                        expert.append(
                            {
                                list(score.children)[0].getText(): {
                                    "class": "overall",
                                    "score": list(score.children)[1].getText(),
                                    "expert_review": list(content.children)[0].getText()
                                }
                            }
                        )

                    return expert
                if len(page_soup.select("div.truncated-content")) > 0:
                    sentences = list(page_soup.find("div", class_="truncated-content").children)
                    temp = sentences.copy()
                    for sentence in temp:
                        if sentence.find("h2") is None:
                            sentences.pop(sentences.index(sentence))

                    return dict(map(lambda rating: (rating.find("h2").getText(),
                                                    [text.text for text in rating.find_all("p") if rating.find_all("p") is not None]), sentences))

                else:  # 2019년..
                    scorecard_dict = dict()
                    for key in self.attributes:
                        scorecard_ = page_soup.find('div', id='{}-section'.format(key.capitalize()))
                        scorecard_dict[key] = scorecard_.find("span").getText()

        except Exception:
            return {"TBD": "TBD"}

        expert = dict()
        keys = list(scorecard_dict.keys())
        keys.remove("overall") if "overall" in keys else keys
        keys.remove("Overall") if "Overall" in keys else keys

        for key in keys:
            expert_soup = page_soup.find('div', id='{}-section'.format(key.capitalize()))
            tuples = []
            for i, h2 in enumerate([h2.getText() for h2 in expert_soup.find_all('h2')]):
                if len(expert_soup.find_all('h2')) == 1:
                    tuples.append(
                        {
                            "class": "{}-overall".format(h2),
                            "score": float(expert_soup.find('span').getText()),
                            "expert_review": expert_soup.find("p").getText() if expert_soup.find("p") is not None else expert_soup.find("div", class_="size-16").getText()
                        }
                    )
                else:
                    if len(expert_soup.find_all("div", "editorial-review-section")) > 0:
                        tuples.append(
                            {
                                "class": "{}-overall".format(h2) if i == 0 else h2,
                                "score": float(expert_soup.find('span').getText()) if i == 0
                                else (expert_soup.find_all("div", "editorial-review-section")[i - 1].find("span").getText() if expert_soup.find_all("div", "editorial-review-section")[i - 1].find("span") is not None else ""),
                                "expert_review": expert_soup.find('div', class_="size-16").getText() if i == 0
                                else expert_soup.find_all("div", "editorial-review-section")[i - 1].find("div", class_="size-16").getText()
                            }
                        )
                    else:  # 2019...
                        tuples.append(
                            {
                                "class": "{}-overall".format(h2) if i == 0 else h2,
                                "score": (float(list(expert_soup.children)[0].find('span').getText()) if list(expert_soup.children)[0].find('span') else "") if i == 0 else float(list(expert_soup.children)[2].find_all("div", id=h2)[0].find('span').getText()),
                                "expert_review": list(expert_soup.children)[1].getText() if i == 0 else list(expert_soup.children)[2].find_all("div", id=h2)[0].getText()
                            }
                        )
            expert[key.capitalize()] = tuples

        return expert

    def get_keywords_in_reviews(self, page_soup):
        try:
            for ___ in page_soup.select("section.consumer-review-aspect-filter-buttons")[0].find_all('div', class_="row"):
                pro_cons = list(___.children)
                # class_condition = pro_cons[1].has_attr('class')
                pro_condition = "Pros" in pro_cons[0].text
                con_condition = 'Cons' in pro_cons[1].text

                tPROS = [button.text for button in pro_cons[0].find_all("button")] if pro_condition else "NA"
                tCONS = [button.text for button in pro_cons[1].find_all("button")] if con_condition else "NA"
        except IndexError:
            tPROS = "NA"
            tCONS = "NA"
        except AttributeError:
            tPROS = "NA"
            tCONS = "NA"

        return tPROS, tCONS

    def get_consumer_ratings(self, page_soup):

        consumers = list()

        if page_soup.find('h3').getText()[:29] == "There are no consumer reviews":
            return {"consumers": "No Consumer Reviews"}

        else:
            reviews = page_soup.find_all('div', class_="review-item")
            for review in reviews:
                review_title = review.find('h3').getText()
                try:
                    name_date_type = review.find('div', class_="small").getText()
                    consumer_name = name_date_type.split(",")[0].strip()
                    date = re.search(r"\d{2}/\d{2}/\d{4}", name_date_type).group()
                    car_type = name_date_type.replace(date, "").split(",")[1].strip()
                except AttributeError as e:
                    print(e)
                    consumer_name = ""
                    date = ""
                    car_type = ""
                try:
                    helpful_index = re.findall("\d+", review.find('div', class_="xsmall").getText())
                    how_helpful = {"Yes": int(helpful_index[0]), "No": int(helpful_index[1]) - int(helpful_index[0])}
                except AttributeError as e:
                    how_helpful = ""
                try:
                    consumer_review = review.find("p").getText()
                except AttributeError as e:
                    consumer_review = ""

                evaluation = dict(map(lambda rating: (rating.find('dt').get_text(), float(rating.find('span').attrs['aria-label'].split(' ')[0])), review.find_all("dl")))
                evaluation.update({'overall': float(review.find('span', class_="rating-stars").attrs['aria-label'].split(' ')[0])})
                consumers.append(
                    {
                        "name": consumer_name,
                        "title": review_title,
                        "date": date,
                        "type": car_type,
                        "consumers_reviews": consumer_review,
                        "Howhelpful": how_helpful,
                        "evaluation": evaluation
                    }
                )
        return consumers

    def get_pros_cons(self, page_soup):
        pros = []
        cons = []

        for __ in page_soup.select('li.pro-con-li span'):
            pro_con_list = list(__.children)
            class_condition = pro_con_list[0].has_attr('class')
            pro_condition = 'icon-checkmark' in pro_con_list[0]['class']
            con_condition = 'icon-cross3' in pro_con_list[0]['class']
            if class_condition and pro_condition:
                pros.append(pro_con_list[1])
            elif class_condition and con_condition:
                cons.append(pro_con_list[1])
            else:
                pros.append("no info")
                cons.append("no info")

        return pros, cons

    def get_data(self, dic):
        dataset = []
        for maker in dic.keys():
            for model in dic[maker].keys():
                for year in dic[maker][model]:
                    if int(year) < 2010:
                        continue

                    if model == "fortwo":
                        url = self.base_url + maker + "/" + model + "/" + year + "/" + "electric"
                    if maker == "porsche" or maker == "mini":
                        url = self.base_url + maker + "/" + model + "/" + year + "/" + "hybrid"
                    else:
                        url = self.base_url + maker + "/" + model + "/" + year + "/" + "review"
                    print('trying {}...'.format(url))

                    page = requests.get(url, headers=self.header)

                    if page.status_code != 200:
                        print("Unable to load webpage: {} Status Code: {}".format(url, page.status_code))
                        continue

                    print('....main page 진행 중')
                    page_soup = BeautifulSoup(page.content, 'lxml')

                    # ====== main-info Scraping =======
                    # - expert info
                    expert = self.get_expert_review(page_soup)
                    # - main info
                    data = self.get_main_info(page_soup)
                    # - Pros and Cons
                    pros, cons = self.get_pros_cons(page_soup)

                    consumer_section = page_soup.select('section.consumer-reviews')

                    # - get feature spec
                    url = '/'.join(url.split('/')[:-1]) + '/features-specs'
                    feature_page = requests.get(url, headers=self.header)
                    time.sleep(2)
                    feature_page_soup = BeautifulSoup(feature_page.content, 'lxml')
                    if feature_page_soup is not None:
                        print('....feature page 진행 중')
                        feature, price = self.get_feature(feature_page_soup)
                    else:
                        feature = "Not described"
                        price = "Not described"

                    # ====== customer-reviews Scraping =======
                    # - pro & cons keywords in reviews

                    # - customer reviews
                    consumers_reviews = []
                    trending_topic_pros = ""
                    trending_topic_cons = ""
                    if consumer_section[0].find("h3").text[:29] == "There are no consumer reviews":
                        pass

                    else:
                        url = '/'.join(url.split('/')[:-1]) + '/consumer-reviews'
                        review_page = requests.get(url, headers=self.header)
                        review_page_soup = BeautifulSoup(review_page.content, 'lxml')

                        trending_topic_pros, trending_topic_cons = self.get_keywords_in_reviews(review_page_soup)

                        links = self.get_nav_links(url)
                        for link in links:
                            link = self.base_url + link
                            review_page = requests.get(link, headers=self.header)
                            time.sleep(4)

                            if review_page.status_code != 200:
                                print("Unable to load webpage: {}. Status Code: {}".format(url, review_page.status_code))
                                continue

                            print('...customer_review page 진행 중')
                            review_page_soup = BeautifulSoup(review_page.content, 'lxml')

                    # - Consumer Ratings
                            consumers = self.get_consumer_ratings(review_page_soup)
                            consumers_reviews.extend(consumers)

                    data.update(
                        {
                            "maker": maker,
                            "model": model,
                            "production_year": year,
                            "price": price,
                            "trending_topic": {"pros": trending_topic_pros, "cons": trending_topic_cons},
                            "pros": pros,
                            "cons": cons,
                            "expert": expert,
                            "features": feature,
                            "consumers": consumers_reviews
                        }
                    )
                    dataset.append(data)
                    time.sleep(5)
                    self.save(dataset, str(maker)+"_"+str(model)+"_"+str(year))

        return dataset

    def save(self, data, filename="final"):  # Convert to Json
        with open(self.res_path + "/res/data_{}.json".format(filename), "w") as json_file:
            json.dump(data, json_file)


if __name__ == '__main__':
    try:
        edmunds = Edmunds()
        # lists = edmunds.get_crawl_list()
        # edmunds.save(lists)
        with open("./EV_lists.json", "r", encoding="utf-8") as json_file:
            lists = json.load(json_file)

        dataset = edmunds.get_data(lists)

    except:
        print("An error has occured. See traceback below: \n")
        print(traceback.print_exc(10))