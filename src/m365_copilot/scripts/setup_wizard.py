"""
M365 Copilot 一键配置向导
运行: python -m m365_copilot.scripts.setup
"""
import os, sys, json, hashlib, base64, uuid, ssl, urllib.request, urllib.parse, webbrowser

CLIENT_ID = "4765445b-32c6-49b0-83e6-1d93765276ca"
SCOPE = "https://substrate.office.com/sydney/.default openid profile offline_access"
TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
AUTHORIZE_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data", "tokens")
ENV_FILE = os.path.join(BASE_DIR, ".env")


def step(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def get_tenant_and_oid():
    step("步骤 1: 获取 Tenant ID 和 User OID")
    print()
    print("在浏览器中登录 https://m365.cloud/microsoft")
    print("然后打开 DevTools (F12) → Console, 粘贴运行这一行:")
    print()
    print("  let k=Object.keys(localStorage).find(k=>k.startsWith('msal.')&&k.includes('|'));let p=k.split('|')[1].split('.');console.log('OID:',p[0]);console.log('TENANT:',p[1]);")
    print()
    tenant = input("请输入 Tenant ID: ").strip()
    oid = input("请输入 User OID:  ").strip()

    if not tenant or not oid:
        print("错误: Tenant ID 和 OID 不能为空")
        sys.exit(1)

    return tenant, oid


def get_refresh_token(tenant):
    step("步骤 2: 获取 Refresh Token (Auth Code + PKCE)")
    print()
    print("将打开浏览器登录 Microsoft 账户。登录后从地址栏复制 code 参数。")

    verifier = base64.urlsafe_b64encode(uuid.uuid4().bytes * 6).rstrip(b'=').decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b'=').decode()

    params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'response_mode': 'fragment',
        'scope': SCOPE,
        'redirect_uri': 'https://m365.cloud.microsoft',
        'state': uuid.uuid4().hex,
        'nonce': uuid.uuid4().hex,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'prompt': 'select_account',
    }

    auth_url = AUTHORIZE_URL.format(tenant=tenant) + "?" + urllib.parse.urlencode(params)
    print(f"\n浏览器链接: {auth_url}\n")

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    code = input("请输入授权 code (从浏览器地址栏 #code=... 复制): ").strip()
    if not code:
        print("错误: 未输入 code")
        sys.exit(1)

    data = urllib.parse.urlencode({
        'client_id': CLIENT_ID,
        'code': code,
        'redirect_uri': 'https://m365.cloud.microsoft',
        'grant_type': 'authorization_code',
        'code_verifier': verifier,
    }).encode()

    token_url = TOKEN_URL.format(tenant=tenant)
    req = urllib.request.Request(token_url, data=data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req.add_header('Origin', 'https://m365.cloud.microsoft')

    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context()) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        print(f"获取 token 失败: {err.get('error')}: {err.get('error_description', '')[:200]}")
        sys.exit(1)

    if 'refresh_token' not in result:
        print("错误: 响应中未包含 refresh_token")
        sys.exit(1)

    return result['refresh_token']


def save_config(tenant, oid, refresh_token):
    step("步骤 3: 保存配置")
    print()

    os.makedirs(DATA_DIR, exist_ok=True)

    # 保存 refresh token (加密存储)
    from .crypto import encrypt as _enc
    rt_file = os.path.join(DATA_DIR, "rt_90day.txt")
    with open(rt_file, 'w') as f:
        f.write(_enc(refresh_token))
    print(f"  Refresh token -> {rt_file} (AES-128-CBC encrypted)")

    # 保存 .env
    env_content = f"""# M365 Copilot Configuration
M365_TENANT_ID={tenant}
M365_USER_OID={oid}
M365_CLIENT_ID={CLIENT_ID}
"""
    with open(ENV_FILE, 'w') as f:
        f.write(env_content)
    print(f"  环境变量     → {ENV_FILE}")

    # 验证 token 可用
    print("\n  验证 token...")
    try:
        sys.path.insert(0, os.path.join(BASE_DIR, "src"))
        from m365_copilot.auth import TokenManager

        cache_file = os.path.join(DATA_DIR, "token_cache.json")
        os.environ['M365_TENANT_ID'] = tenant
        os.environ['M365_USER_OID'] = oid

        tm = TokenManager(tenant, CLIENT_ID, SCOPE, rt_file, cache_file)
        access_token = tm.get()
        print(f"  ✓ Token 验证成功 (长度: {len(access_token)})")
    except Exception as e:
        print(f"  ✗ Token 验证失败: {e}")
        sys.exit(1)


def main():
    print("=" * 60)
    print("  M365 Copilot 配置向导 v1.0")
    print("=" * 60)
    print()
    print("此脚本将引导你完成以下步骤:")
    print("  1. 获取 Tenant ID 和 User OID")
    print("  2. 通过浏览器登录获取 Refresh Token")
    print("  3. 保存配置并验证")

    tenant, oid = get_tenant_and_oid()

    print(f"\n  Tenant ID: {tenant}")
    print(f"  User OID:  {oid}")

    confirm = input("\n确认无误? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        sys.exit(0)

    refresh_token = get_refresh_token(tenant)
    save_config(tenant, oid, refresh_token)

    step("配置完成!")
    print()
    print("使用方式:")
    print("  python -m m365_copilot \"你好\"           # CLI 提问")
    print("  python -m m365_copilot -i                 # 交互模式")
    print("  python -m m365_copilot --list-models      # 列出模型")
    print()
    print("环境变量已保存到 .env, 每次运行会自动加载。")


if __name__ == "__main__":
    main()
