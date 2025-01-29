from pydantic import BaseModel
class Config(BaseModel):
    mikan_url : str = "http://mikanani.me"  # 如果连接不上，可换镜像站