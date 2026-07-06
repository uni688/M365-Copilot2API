import sys, os, json
sys.path.insert(0, r"D:\sj\M365-Copilot2API\src")
os.environ['M365_TENANT_ID'] = 'a636d8ab-26fd-41a5-b1bb-1f28c3363342'
os.environ['M365_USER_OID'] = '7da2b135-7ed7-4f5c-9520-b5b2daf9d64a'

from m365_copilot.payload import build_conversation_payload

# 模拟多轮对话
messages = [
    {"role": "user", "content": "我叫小明，我喜欢吃苹果"},
    {"role": "assistant", "content": "你好小明！很高兴认识你。苹果确实是一种很健康的水果。"},
    {"role": "user", "content": "我刚才说我叫什么？"},
]

p = json.loads(build_conversation_payload("a"*32, "b"*32, messages))
print("message.text:", p["arguments"][0]["message"]["text"])
print("messageHistory:")
for h in p["arguments"][0].get("messageHistory", []):
    author = h.get("author", "?")
    text = h.get("text", "")[:50]
    print(f"  {author}: {text}")
