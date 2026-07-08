"""
M365 Copilot 一键配置向导
运行: python -m m365_copilot.scripts.setup
"""
import os, sys, json, base64

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CLIENT_ID = "c0ab8ce9-e9a0-42e7-b064-33d422df41f1"
SCOPE = "https://substrate.office.com/sydney/.default openid profile offline_access"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data", "tokens")
ENV_FILE = os.path.join(BASE_DIR, ".env")


def step(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def _decode_jwt_payload(token):
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    payload += "=" * (4 - len(payload) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def main():
    print("=" * 60)
    print("  M365 Copilot 配置向导")
    print("=" * 60)

    os.makedirs(DATA_DIR, exist_ok=True)
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    from m365_copilot.auth import TokenManager

    rt_file = os.path.join(DATA_DIR, "rt_90day.txt")
    cache_file = os.path.join(DATA_DIR, "token_cache.json")

    tm = TokenManager("common", CLIENT_ID, SCOPE, rt_file, cache_file)

    step("浏览器认证")
    print("\n将自动打开浏览器进行 Microsoft 登录...")
    result = tm.setup()
    if not result:
        print("\n认证失败")
        sys.exit(1)

    if isinstance(result, dict) and "id_token" in result:
        payload = _decode_jwt_payload(result["id_token"])
        tenant = payload.get("tid", "")
        oid = payload.get("oid", "")
    else:
        tenant = input("\n请输入你的 Tenant ID: ").strip()
        oid = input("请输入你的 User OID: ").strip()

    if not tenant or not oid:
        print("错误: 未能获取 tenant/oid")
        sys.exit(1)

    os.environ["M365_TENANT_ID"] = tenant
    os.environ["M365_USER_OID"] = oid

    step("验证 Token")
    tm = TokenManager(tenant, CLIENT_ID, SCOPE, rt_file, cache_file)
    try:
        access_token = tm.get()
        print(f"  ✓ Token 验证成功 (access_token 长度: {len(access_token)})")
    except Exception as e:
        print(f"  ✗ Token 验证失败: {e}")
        sys.exit(1)

    env_content = f"""# M365 Copilot Configuration
M365_TENANT_ID={tenant}
M365_USER_OID={oid}
M365_CLIENT_ID={CLIENT_ID}
"""
    with open(ENV_FILE, "w") as f:
        f.write(env_content)
    print(f"  .env 已保存 → {ENV_FILE}")

    step("配置完成!")
    print()
    print('使用方式:')
    print('  m365-copilot "你好"              # CLI 提问')
    print("  m365-copilot -i                  # 交互模式")
    print("  m365-copilot --list-models       # 列出模型")
    print("  m365-copilot-server --port 8000  # 启动 API 服务")
    print()
    print(f"Token 存储: {DATA_DIR}")
    print(f"配置文件:   {ENV_FILE}")


if __name__ == "__main__":
    main()
