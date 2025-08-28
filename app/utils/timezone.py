from datetime import datetime
from flask import current_app
import pytz

def get_beijing_time(utc_time=None):
    """
    获取北京时区的时间
    :param utc_time: UTC时间，如果为None则使用当前时间
    :return: 北京时区的datetime对象
    """
    if utc_time is None:
        utc_time = datetime.utcnow()
    
    # 确保输入时间是UTC时区
    if utc_time.tzinfo is None:
        utc_time = pytz.UTC.localize(utc_time)
    
    # 转换为北京时区
    beijing_tz = pytz.timezone('Asia/Shanghai')
    beijing_time = utc_time.astimezone(beijing_tz)
    
    return beijing_time

def format_beijing_time(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """
    格式化北京时区时间
    :param dt: datetime对象
    :param format_str: 格式化字符串
    :return: 格式化后的时间字符串
    """
    beijing_time = get_beijing_time(dt)
    return beijing_time.strftime(format_str)

def get_current_beijing_time():
    """
    获取当前北京时区时间
    :return: 当前北京时区的datetime对象
    """
    return get_beijing_time()

def format_relative_time(dt):
    """
    格式化相对时间（如：刚刚、5分钟前、1小时前等）
    :param dt: datetime对象
    :return: 相对时间字符串
    """
    beijing_time = get_beijing_time(dt)
    now = get_current_beijing_time()
    
    diff = now - beijing_time
    
    if diff.total_seconds() < 60:
        return "刚刚"
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() / 60)
        return f"{minutes}分钟前"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"{hours}小时前"
    else:
        days = int(diff.total_seconds() / 86400)
        return f"{days}天前"
