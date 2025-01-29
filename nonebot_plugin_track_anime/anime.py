import base64
from bs4 import BeautifulSoup
import datetime
from playwright.async_api import async_playwright
import asyncio
from .config import Config
config = Config()

from nonebot.log import logger

_mikan_url = config.mikan_url

class Bangumi:
    def __init__(self, name: str, update_time: datetime.date, url: str):
        self.name = name
        self.update_time = update_time
        self.url = url
        self.poster_url = None
        self.bangumi_link = None  
        self.rating_score = None  
        self.rating_description = None  
        self.shoot = None 

    async def fetch_bangumi_info(self, page):
        """从番剧的 URL 中提取 Bangumi 番组计划链接，并获取评分信息"""
        if not self.url:
            logger.error(f"No URL found for {self.name}")
            return

        # 使用 Playwright 访问番剧详情页
        await page.goto(self.url)
        content = await page.content()
        soup = BeautifulSoup(content, "html.parser")

        # 提取 Bangumi 番组计划链接
        bangumi_info_list = soup.find_all("p", class_="bangumi-info")
        for bangumi_info in bangumi_info_list:
            if "Bangumi番组计划链接" in bangumi_info.text:
                bangumi_link_tag = bangumi_info.find("a", class_="w-other-c")
                if bangumi_link_tag:
                    self.bangumi_link = bangumi_link_tag["href"]

        # 访问 Bangumi 页面并提取评分信息
        if self.bangumi_link:
            await page.goto(self.bangumi_link)
            await page.wait_for_timeout(5000)  # 等待页面加载

            # 提取评分信息
            rating_div = await page.query_selector("div[rel='v:rating']")
            if rating_div:
                rating_score = await rating_div.query_selector("span.number")
                rating_description = await rating_div.query_selector("span.description")
                self.rating_score = await rating_score.inner_text()
                self.rating_description = await rating_description.inner_text()
            else:
                logger.error(f"No rating found for {self.name}")
            target_div = page.locator('div.subject_tag_section')
            await target_div.wait_for(state='visible')
            div = await target_div.screenshot()
            self.shoot = base64.b64encode(div).decode()

class HomePage:
    """表示 Mikanani 主页的类"""
    def __init__(self):
        self.periods = []
        self.period = ""
        self._reset_bangumi_data()

    def _reset_bangumi_data(self):
        """重置番剧数据"""
        self.mon = []
        self.tue = []
        self.wed = []
        self.thu = []
        self.fri = []
        self.sat = []
        self.sun = []

    def _find_target(self, weekday: str):
        """根据星期几返回对应的番剧列表"""
        if weekday == "星期一":
            return self.mon
        elif weekday == "星期二":
            return self.tue
        elif weekday == "星期三":
            return self.wed
        elif weekday == "星期四":
            return self.thu
        elif weekday == "星期五":
            return self.fri
        elif weekday == "星期六":
            return self.sat
        elif weekday == "星期日":
            return self.sun
        else:
            return None

    def feed_p(self, soup: BeautifulSoup):
        """从 BeautifulSoup 对象中提取番剧数据"""
        subsoups = soup.find_all("div", "m-home-week-item")  # 找到所有番剧容器
        for subsoup in subsoups:
            weekday = subsoup.find("span", "monday").text.strip()  # 提取星期几
            target = self._find_target(weekday)  # 获取目标列表
            if target is None:
                continue  # 跳过非星期几的番剧

            items = subsoup.find_all("div", "m-week-square")  # 找到所有番剧信息
            for item in items:
                a_tag = item.find("a", title=True)  # 找到包含标题的 <a> 标签
                if a_tag is None:
                    continue  # 如果 a_tag 不存在，跳过该番剧

                title = a_tag["title"]  # 提取标题
                img_tag = a_tag.find("img")  # 找到图片标签
                img_src = img_tag["data-src"] if img_tag and "data-src" in img_tag.attrs else None  # 提取图片链接

                
                bangumi = Bangumi(
                    name=title,
                    update_time=datetime.date.today(),  
                    url=_mikan_url + a_tag["href"] if a_tag["href"] else None  
                )
                bangumi.poster_url = _mikan_url+img_src  # 添加图片链接
                target.append(bangumi)

    def feed(self, soup: BeautifulSoup):
        psoup = soup.find("li", "sk-col dropdown date-btn")
        if psoup is not None:
            self.period = psoup.find_next("div", "sk-col date-text").contents[0].strip()
            periods = psoup.find_all(lambda tag: tag.name == "a" and tag.has_attr("data-season"))
            for p in periods:
                self.periods.append("{0} {1}".format(p["data-year"], p.contents[0].strip()))
        self._reset_bangumi_data()  # 重置番剧数据
        self.feed_p(soup)  # 提取番剧数据

async def get_homepage(page):
    await page.goto(_mikan_url)
    content = await page.content()
    soup = BeautifulSoup(content, "html.parser")
    hp = HomePage()
    hp.feed(soup)
    return hp