# -*- coding: utf-8 -*-

from crawl_edmunds import Edmunds
import requests
from bs4 import BeautifulSoup
import time
import json
import traceback


class Carsdotcom(Edmunds):

    def __init__(self):
        Edmunds.__init__(self)
        self.base_url = "https://www.cars.com"
        self.sub_url_EV = "/research/search/?rn=0&rpp=13&highMpgId=1836,1838"
        self.res_path = "../../data/Carsdotcom"

        page = requests.get(self.base_url + self.sub_url_EV, headers=self.header)
        page_soup = BeautifulSoup(page.content, 'lxml')
        soup_make = page_soup.find_all("div", class_="menu__content")
        for make in soup_make[3].find_all("label", class_="checkbox__label"):
            if make.getText() not in self.makers:
                self.makers.append(make.getText())
        self.makers.remove("Any")

    def get_crawl_list(self):  # for only e-car

        page = requests.get(self.base_url + self.sub_url_EV, headers=self.header)
        time.sleep(3)
        page_soup = BeautifulSoup(page.content, 'lxml')
        term = int(page_soup.find("div", class_="page-buttons").find("a")["href"].split("=")[-1])
        base = page_soup.find("div", class_="page-numbers").find("a")["href"]
        nav_links = [base.replace("0", "{}").format(str(term*page_num))
                     for page_num in range(1, int(page_soup.find("div", class_="page-numbers").find_all("a")[-1].getText()))]
        nav_links.insert(0, base)

        crawl_lists = list()
        for nav_link in nav_links:
            page = requests.get(self.base_url + "/" + nav_link, headers=self.header)
            time.sleep(2)
            page_soup = BeautifulSoup(page.content, 'lxml')
            lists = page_soup.find_all("div", class_="listingCard")
            for lst in lists:
                crawl_lists.append(lst.find("a")["href"])

        return crawl_lists

    def get_main_info(self, page_soup):
        # img = page_soup.find("div", class_="mmy-impression__image").find("img").attrs["src"]
        try:
            make_model_year = page_soup.find("h1", class_="cui-page-section__title").getText()
            year = make_model_year.split(" ")[0]
            make = make_model_year.split(" ")[1]
            model = "-".join(make_model_year.split(" ")[2:]).lower()
        except AttributeError:
            print("proxy error")
            return "proxy error"
        try:
            car_type = page_soup.select("div.list-specs__value")[0].getText().strip()
        except IndexError:
            car_type = "TBD"
        price = page_soup.find("div", class_="mmy-header__msrp").getText().strip()

        pros_cons_opinion = page_soup.select("div.mmy-impression__feature-column")
        [pros, cons] = [[li.getText() for li in pros_cons.find_all("li")] for pros_cons in pros_cons_opinion] if pros_cons_opinion else ["", ""]
        what_to_know = [div.getText() for div in page_soup.select("ul.list-checklist")[0].find_all("div", class_="list-checklist-label")] if page_soup.select("ul.list-checklist") else ""

        expert_soup = page_soup.find("div", class_="mmy-expert__excerpt-review q-and-a")
        if expert_soup:
            overall_list = [v.getText() for v in list(expert_soup.children) if v != "\n"]
            questions = [(idx, children) for idx, children in enumerate(overall_list) if children.endswith("?")]

            order = 0
            temp_key = ""
            expert = dict()
            for idx, content in enumerate(overall_list):
                if idx in [q[0] for q in questions]:
                    temp_key = questions[order][1]
                    expert[temp_key] = ""
                    order += 1
                else:
                    expert[temp_key] += content
        else:
            expert = ""

        return {
            # "img": img,
            "what_to_know": what_to_know,
            "maker": make,
            "model": model,
            "production_year": year,
            "type": car_type,
            "price": price,
            "pros": pros,
            "cons": cons,
            "expert": expert
        }

    def get_consumer_ratings(self, page_soup):
        consumers = list()

        if page_soup is None:
            return {"consumers": "No Consumer Reviews"}

        if page_soup:
            reviews = page_soup.find_all("article", class_="review-listing-card")
            for review in reviews:
                review_title = review.find("p", class_="cui-heading-6").getText()
                try:
                    name_date = review.find("p", class_="review-card-review-by").getText().strip().split(" ")
                    consumer_name = name_date[1]
                    date = " ".join(name_date[-3:])
                except AttributeError as e:
                    print(e)
                    consumer_name = ""
                    date = ""

                consumer_review = review.find("p", class_="review-card-text").getText().strip()
                evaluation = dict(map(lambda rating: (rating.find("span").getText(), float(rating.find("cars-star-rating").attrs["rating"])), [a for a in list(review.find("div").children) if a != "\n" and a.find("cars-star-rating").attrs["rating"] != ""]))
                evaluation.update(
                    {'overall': float(review.find("cars-star-rating").attrs["rating"])})
                context = [context.getText() for context in review.find_all("p", class_="review-card-extra")] if review.find("p", class_="review-card-extra") else ""
                if review.find("p", class_="review-card-feedback").getText() != "Did you find this review helpful?":
                    helpful_index = review.find("p", class_="review-card-feedback").find_all("b")
                    how_helpful = {"Yes": int(helpful_index[0].getText()),
                                   "No": int(helpful_index[1].getText()) - int(helpful_index[0].getText())}
                else:
                    how_helpful = ""
                consumers.append(
                    {
                        "name": consumer_name,
                        "title": review_title,
                        "date": date,
                        "consumers_reviews": consumer_review,
                        "Howhelpful": how_helpful,
                        "evaluation": evaluation,
                        "context": context
                    }
                )

            return consumers

    def get_data(self, sub_url):
        print('trying {}...'.format(sub_url))
        # ====== main-info Scraping =======
        main_page = requests.get(self.base_url + sub_url, headers=self.header)
        time.sleep(2)
        main_page_soup = BeautifulSoup(main_page.content, 'lxml')
        print('....main page 진행 중')
        data = self.get_main_info(main_page_soup)

        # ====== customer-reviews Scraping =======
        # - customer reviews
        if main_page_soup.find("span", class_="rating__info"):
            sub_url_ = sub_url + 'consumer-reviews/'
            review_page = requests.get(self.base_url + sub_url_, headers=self.header)
            time.sleep(2)
            review_page_soup = BeautifulSoup(review_page.content, 'lxml')

            max_num = 1
            if review_page_soup.find("div", class_="page-numbers"):
                max_num = int(review_page_soup.find("div", class_="page-numbers").find_all("a")[-1].getText())

            nav_links = [sub_url_ + "?pg={}&rn=10".format(str(page_num)) for page_num in range(1, max_num+1)]

            consumers_reviews = []

            for nav_link in nav_links:
                review_page = requests.get(self.base_url + nav_link, headers=self.header)
                time.sleep(2)
                review_page_soup = BeautifulSoup(review_page.content, 'lxml')
                print('...customer_review page {} / {} 진행 중'.format(nav_links.index(nav_link)+1, max_num))
                time.sleep(3)
                consumers = self.get_consumer_ratings(review_page_soup)
                consumers_reviews.extend(consumers)
            data.update(
                {
                    "consumers": consumers_reviews
                }
            )
            time.sleep(5)

        return data


if __name__ == "__main__":
    try:
        carsdotcom = Carsdotcom()

        # extracting crawl lists at category "green car"
        # target = carsdotcom.get_crawl_list()
        # carsdotcom.save(target, "EV_lists_carsdotcom")
        # with open("./crawl_list.json", "r", encoding="utf-8") as json_file:
        #     crawl_list = json.load(json_file)

        # dataset = list()
        # for i, sub_url in enumerate(crawl_list):
        #     dataset.append(carsdotcom.get_data(sub_url))
        #     with open("./res/data/dataset_{}.json".format(str(i)), "w", encoding="utf-8") as json_file:
        #         json.dump(dataset, json_file)

        # crawl by "maker / model / production-year"
        with open("./EV_lists_cardotcom.json", "r", encoding="utf-8") as json_file:
            EV_list = json.load(json_file)

        dataset = list()
        for maker in EV_list.keys():
            for model in EV_list[maker].keys():
                for year in EV_list[maker][model]:
                    model = model.replace("-", "_")
                    sub_url = "/research/" + maker.lower() + "-" + model + "-" + year + "/"
                    a_car = carsdotcom.get_data(sub_url)
                    if a_car == "proxy error":
                        continue
                    dataset.append(a_car)
                    with open(carsdotcom.res_path + "/res/data_{}_{}_{}.json".format(maker, model, year), "w", encoding="utf-8") as json_file:
                        json.dump(dataset, json_file)

    except:
        print("An error has occured. See traceback below: \n")
        print(traceback.print_exc(10))
