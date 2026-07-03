import datetime, random

from .provider import provider


@provider.register(name="get_current_time", description="获取当前日期和时间")
def get_current_time() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@provider.register(name="calculate", description="执行数学计算")
def calculate(expression: str) -> str:
    allowed = set("0123456789+-*/(). ")
    if not all(c in allowed for c in expression):
        return "错误：表达式包含不允许的字符"
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误: {e}"


@provider.register(name="roll_dice", description="掷骰子")
def roll_dice(sides: int = 6) -> str:
    result = random.randint(1, sides)
    return f"Rolled {result} (d{sides})"
