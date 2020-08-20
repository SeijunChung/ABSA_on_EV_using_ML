# -*- coding: utf-8 -*-

from crawl_edmunds import Edmunds
import time
import re
import requests
from bs4 import BeautifulSoup
import json
import traceback


class Cargurus(Edmunds):

    def __init__(self):
        Edmunds.__init__(self)
        self.base_url = "https://www.cargurus.com"
        self.sub_url = "/Cars/autos/"
        self.res_path = "../../data/Cargurus"
        print(self.header)

        page = requests.get(self.base_url + self.sub_url, headers=self.header)
        page_soup = BeautifulSoup(page.content, 'lxml')

        self.links_maker = page_soup.find_all("div", class_="cg-research-listing")
        self.links = [link.find("a").attrs["href"] for link in self.links_maker if link.find("a").getText() in self.makers]
        print(self.links)

    def get_crawl_list(self, default_lists):
        crawl_lists = list()
        fail_lists = list()
        for link in self.links:
            maker = link.split("-")[0].split("/")[-1]
            models = [model for model in default_lists[maker].keys()]

            page = requests.get(self.base_url + link, headers=self.header)
            page_soup = BeautifulSoup(page.content, 'lxml')
            time.sleep(2)
            available = page_soup.find("div", id="makeOverviewAvailableModels")
            if len(available.find_all("div", class_="entityTitle")) > 0:
                link_models = list(map(lambda x: x.find("a").attrs["href"],
                                    page_soup.find("div", id="makeOverviewAvailableModels").find_all("div", class_="entityTitle")))
            else:
                link_models = list(map(lambda x: x.find("a").attrs["href"],
                                       page_soup.find("div", id="makeOverviewAvailableModels").find_all("li")))

            for model in models:
                if model.lower() in ["ioniq-ev", "kona-ev"]:
                    model = model.replace("ev", "electric")
                    # print(model)
                if "plug-in-hybrid" in model or "outlander" in model:
                    model = "plug-in"
                for link_model in link_models:
                    if model.lower() in link_model.lower():
                        # print(self.base_url + link)
                        page = requests.get(self.base_url + link, headers=self.header)
                        page_soup = BeautifulSoup(page.content, "lxml")
                        time.sleep(2)

                        print(requests.get(page_soup.find_all("li")))
                        try:
                            page = requests.get(self.base_url + page_soup.find_all("li", property="itemListElement")[3].find("a").attrs["href"], headers=self.header)
                            page_soup = BeautifulSoup(page.content, 'lxml')

                        except AttributeError:
                            print(model)
                        for yrs in page_soup.find_all("div", class_="entityTitle"):
                            print(yrs)
                            try:
                                if "href" in yrs.find("a").attrs:
                                    crawl_lists.append(yrs.find("a").attrs["href"])
                                else:
                                    fail_lists.append(yrs.getText())
                            except AttributeError:
                                fail_lists.append(yrs.getText())
        return crawl_lists, fail_lists

    def get_crawl_lists(self):
        page = requests.get(self.base_url + '/Cars/2020-Audi-e-tron-Overview-c29884', headers=self.header)
        page_soup = BeautifulSoup(page.content, 'lxml')
        print(page_soup.find_all("li", property="itemListElement")[3].find("a").attrs["href"])

    def get_main_info(self, page_soup):
        try:
            make_model_year = page_soup.find("h1", class_="cg-accent").getText()
            year = make_model_year.split(" ")[0]
            make = make_model_year.split(" ")[1]
            model = "-".join([w for w in make_model_year.split(" ")[2:] if w not in ["User", "Reviews"]]).lower()

        except AttributeError as e:
            make = ""
            model = ""
            year = ""

        return {
            "maker": make,
            "model": model,
            "year": year
        }

    def get_consumer_ratings(self, page_soup):
        consumers = list()
        tobe = list()
        if page_soup:
            reviews = page_soup.find_all("div", class_="cg-user-review-container")
            if len(reviews) == 10:
                tobe.append(page_soup.find("h1", class_="cg-accent").getText())

            for review in reviews:
                consumer_name = ""
                consumer_review = ""
                consumer_review2 = ""
                consumer_pick = ""
                if review.find("div", class_="cg-user-review-author"):
                    if review.find("div", class_="cg-user-review-author").find("span", property="name"):
                        consumer_name = review.find("div", class_="cg-user-review-author").find("span", property="name").getText()
                if review.find("div", class_="cg-userReviewBody"):
                    rb = review.find("div", class_="cg-userReviewBody")
                    if rb.find("blockquote", class_="category-comment"):
                        print("case1")
                        consumer_review = rb.find("blockquote", class_="category-comment").getText()
                        print(consumer_review)
                    elif rb.find("p", class_="cg-user-review-truncated"):
                        if rb.find("p", class_="cg-user-review-truncated").find("span"):
                            consumer_review = rb.find("p", class_="cg-user-review-truncated").find("span").getText()
                            print(consumer_review)
                    elif rb.find("p", class_="cg-userReviewText"):
                        print("case3")
                        consumer_review = rb.find("p", class_="cg-userReviewText").getText()
                        print(consumer_review)
                    else:
                        print("category-comment 없음")
                        consumer_review = rb.getText()
                        print(consumer_review)

                if review.find("div", class_="cg-userReviews"):
                    categories = review.find("div", class_="cg-userReviews")
                    if len(categories.find_all("div", class_="category-review-detail-section")) > 0:
                        picks = categories.find_all("div", class_="category-review-detail-section")
                        consumer_pick = [pick.find("span", class_="criteria-label").getText() for pick in picks]
                        consumer_review2 = " ".join([re.sub(r'^"|"$', '', cat.find("em").getText()) for cat in categories.find_all("blockquote")])
                        print(consumer_review2)
                    elif review.find("div", class_="pros-and-cons"):
                        consumer_review2 = review.find("div", class_="pros-and-cons").getText()
                        print(consumer_review2)
                consumers.append(
                    {
                        "name": consumer_name,
                        "consumer_review": consumer_review + consumer_review2,
                        "aspect": consumer_pick
                    }
                )
        return consumers, tobe

    def get_data(self, sub_url):
        print('trying {}...'.format(sub_url))
        page = requests.get(self.base_url + "/" + sub_url, headers=self.header)
        main_page_soup = BeautifulSoup(page.content, 'lxml')
        time.sleep(3)
        data = self.get_main_info(main_page_soup)
        consumers = ""
        todo = []
        try:
            if "href" in main_page_soup.find("div", class_="subnav").find_all("li")[1].find("a").attrs.keys():
                url = main_page_soup.find("div", class_="subnav").find_all("li")[1].find("a").attrs["href"]
                if "trims" in url.lower():
                    url = sub_url.replace("Overview", "Reviews")
            else:
                url = sub_url.replace("Overview", "Reviews")

            page = requests.get(self.base_url + url, headers=self.header)
            time.sleep(2)
            review_page_soup = BeautifulSoup(page.content, 'lxml')
            consumers, todo = self.get_consumer_ratings(review_page_soup)

        except AttributeError:
            print("{} => User Reviews 없음".format(sub_url))

        data.update(
            {
                "consumers": consumers,
                "to_be_added": todo
            }
        )

        return data


if __name__ == '__main__':
    try:
        cargurus = Cargurus()
        # with open("./EV_lists_edmunds.json", "r", encoding="utf-8") as json_file:
        #     lists = json.load(json_file)
        # dataset, fail = cargurus.get_crawl_list(lists)
        # with open("./EV_lists_cargurus.json", "w", encoding="utf-8") as json_file:
        #     json.dump(dataset, json_file)
        # with open("./res/lists_fails.json", "w", encoding="utf-8") as json_file:
        #     json.dump(fail, json_file)
        # cargurus.get_crawl_lists()
        with open("./EV_lists_cargurus.json", "r", encoding="utf-8") as json_file:
            crawl_lists = json.load(json_file)
        dataset = list()
        for crawl_list in crawl_lists:
            data = cargurus.get_data(crawl_list)
            dataset.append(data)
            year = crawl_list.split("/")[-1].split("-")[0]
            maker = crawl_list.split("/")[-1].split("-")[1]
            model = "".join(crawl_list.split("/")[-1].split("-")[2:-2])
            with open(cargurus.res_path + "/res/data_{}_{}_{}.json".format(maker, model, year), "w", encoding="utf-8") as json_file:
                json.dump(dataset, json_file)
    except:
        print("An error has occured. See traceback below: \n")
        print(traceback.print_exc(10))