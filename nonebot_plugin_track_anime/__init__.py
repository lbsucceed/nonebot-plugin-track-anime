import base64
from nonebot import on_command
from nonebot.plugin import PluginMetadata
from nonebot.adapters import Message
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import (
    Message,
    MessageSegment
)
from playwright.async_api import async_playwright
import httpx
import asyncio
import imageio.v3 as iio
from io import BytesIO
from .config import Config
from .anime import get_homepage


__plugin_meta__ = PluginMetadata(
    name="追番小工具",
    description="通过mikan project进行每日番剧推送： /追番 ",
    usage="发送 /追番 进行指令推送",
    type="application",
    homepage="https://github.com/lbsucceed/nonebot-plugin-track-anime",
    config=Config,
    supported_adapters={"~onebot.v11"}
)


track = on_command("追番", aliases={"track"})


async def fetch_image(url: str) -> bytes:
    """
    异步获取图像数据
    :param url: 图片的 URL
    :return: 图片的二进制数据
    """
    async with httpx.AsyncClient(follow_redirects=True) as client:  # 启用自动重定向
        response = await client.get(url)
        response.raise_for_status()  # 确保请求成功
        return response.content


async def process_image(image_data: bytes) -> str:
    """
    异步处理图像并转换为 Base64
    :param image_data: 图片的二进制数据
    :return: Base64 编码的图片字符串
    """
    image = iio.imread(image_data)  # 读取图片
    with BytesIO() as buffer:
        iio.imwrite(buffer, image, format="PNG")  # 将图片保存为 PNG 格式
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")  # 转换为 Base64
    return image_base64


@track.got("weekday", prompt="请输入需要查询的日期（例：星期一）：")
async def _(state: T_State):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        homepage = await get_homepage(page)
        weekday = str(state["weekday"])
        if weekday not in ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]:
            await track.reject('错误，请重新输入正确的日期')
        target_list = homepage._find_target(weekday)
        message = ""
        for idx, bangumi in enumerate(target_list, start=1):
            message += f"{idx}. {bangumi.name}\n"
        await track.send(Message(message))
        state["page"] = page
        state["target_list"] = target_list
        state["browser"] = browser


@track.got("number", prompt="输入所需要查看番剧的序号")
async def _(state: T_State):
    num = int(str(state["number"]))
    target_list = state["target_list"]

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        if 1 <= num <= len(target_list):
            selected_bangumi = target_list[num - 1]
            name = selected_bangumi.name
            await selected_bangumi.fetch_bangumi_info(page)
            url = selected_bangumi.poster_url

            try:
                # 异步获取并处理图像
                image_data = await fetch_image(url)
                image_base64 = await process_image(image_data)

                link = selected_bangumi.bangumi_link
                description = f"{selected_bangumi.rating_score} ({selected_bangumi.rating_description})"
                shoot = selected_bangumi.shoot

                await track.finish(
                    f"{link}\n"
                    + f"{name}\n"
                    + f"{description}\n"
                    + ("-" * 30) + "\n"
                    + MessageSegment.image(f"base64://{image_base64}") + "\n"
                    + ("-" * 30) + "\n"
                    + MessageSegment.image(f"base64://{shoot}")
                )

            except httpx.HTTPError as e:
                await track.finish(f"获取图片失败: {e}")

            finally:
                await page.close()
                await browser.close()

        else:
            await track.reject('输入的序号无效,请重新输入')