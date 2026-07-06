"""
M365 Copilot 一键配置向导
运行: python -m m365_copilot.scripts.setup
"""
import os, sys, json, re, ssl, urllib.request, urllib.parse, uuid, base64, hashlib

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

CLIENT_ID = "c0ab8ce9-e9a0-42e7-b064-33d422df41f1"
SCOPE = "https://substrate.office.com/sydney/M365Chat.Read https://substrate.office.com/sydney/sydney.readwrite offline_access openid profile"
REDIRECT_URI = "https://login.microsoftonline.com/common/oauth2/nativeclient"
AUTHORIZE_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data", "tokens")
ENV_FILE = os.path.join(BASE_DIR, ".env")


def step(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def extract_from_console_output(raw: str):
    """Parse tenant, oid, refresh_token from browser console output."""
    raw = re.sub(r'^粘贴\s*=>\s*', '', raw)
    raw = re.sub(r'^PS\s+[^>]+>\s*', '', raw)
    raw = re.sub(r'^>\s*', '', raw)

    tenant = oid = refresh_token = None

    m_oid = re.search(r"OID:\s*([a-f0-9-]+)", raw)
    m_tenant = re.search(r"TENANT:\s*([a-f0-9-]+)", raw)
    if m_oid and m_tenant:
        oid = m_oid.group(1)
        tenant = m_tenant.group(1)

    m_rt = re.search(r"REFRESH[_\s]?TOKEN[:\s]+([A-Za-z0-9\-_.]+)", raw)
    if m_rt:
        refresh_token = m_rt.group(1)

    if not refresh_token:
        m_rt2 = re.search(r"refresh[_\s]?token[:\s]+([A-Za-z0-9\-_.]{20,})", raw, re.I)
        if m_rt2:
            refresh_token = m_rt2.group(1)

    if not refresh_token or refresh_token == "NOT_FOUND":
        m = re.search(r"\{", raw)
        if m:
            start = m.start()
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(raw)):
                c = raw[i]
                if escape:
                    escape = False
                    continue
                if c == '\\' and in_string:
                    escape = True
                    continue
                if c == '"' and not escape:
                    in_string = not in_string
                    continue
                if not in_string:
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            try:
                                data = json.loads(raw[start:i+1])
                                tenant = tenant or data.get("tenant")
                                oid = oid or data.get("oid")
                                refresh_token = data.get("refresh_token")
                            except json.JSONDecodeError:
                                pass
                            break

    return tenant, oid, refresh_token


def get_config_from_browser():
    step("步骤 1: 浏览器登录获取授权")
    print()

    verifier = base64.urlsafe_b64encode(os.urandom(64)).rstrip(b'=').decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b'=').decode()

    params = {
        'client_id': CLIENT_ID, 'response_type': 'code',
        'response_mode': 'query',
        'scope': SCOPE,
        'redirect_uri': REDIRECT_URI,
        'state': uuid.uuid4().hex, 'nonce': uuid.uuid4().hex,
        'code_challenge': challenge, 'code_challenge_method': 'S256',
        'prompt': 'select_account',
    }
    url = AUTHORIZE_URL.format(tenant="common") + "?" + urllib.parse.urlencode(params)

    print("请在浏览器中打开以下链接并登录:")
    print()
    print("=" * 60)
    print(url)
    print("=" * 60)
    print()
    print("登录后浏览器会跳转到一个空白页或错误页（这是正常的）")
    print("请复制地址栏的完整 URL 粘贴到下面：")
    print()

    url_input = input("粘贴跳转后的完整 URL: ").strip()
    if not url_input:
        print("错误: 未输入 URL")
        sys.exit(1)

    parsed = urllib.parse.urlparse(url_input)
    code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
    if not code:
        code = urllib.parse.parse_qs(parsed.fragment).get("code", [None])[0]
    if not code:
        print("错误: URL 中未找到 authorization code")
        print("请确认粘贴的是登录后跳转的完整地址栏 URL")
        sys.exit(1)

    step("步骤 2: 交换 Token")
    print()

    data = urllib.parse.urlencode({
        'client_id': CLIENT_ID, 'code': code,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code', 'code_verifier': verifier,
    }).encode()
    req = urllib.request.Request(TOKEN_URL.format(tenant="common"), data=data)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context()) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        print(f"Token 交换失败: {err.get('error')}: {err.get('error_description', '')[:200]}")
        sys.exit(1)

    if 'refresh_token' not in result:
        print(f"Token 交换失败: {result.get('error', '未知错误')}")
        sys.exit(1)

    # Decode JWT to get tenant and oid
    token = result['access_token']
    payload_b64 = token.split('.')[1]
    pad = 4 - (len(payload_b64) % 4)
    if pad != 4:
        payload_b64 += '=' * pad
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload_b64))
        tenant = claims.get('tid', '')
        oid = claims.get('oid', '')
    except Exception:
        tenant = ''
        oid = ''

    if not tenant or not oid:
        print("错误: 无法从 JWT 中解析 tenant/oid")
        print("请手动设置环境变量 M365_TENANT_ID 和 M365_USER_OID")
        tenant = input("Tenant ID: ").strip()
        oid = input("User OID: ").strip()

    return tenant, oid, result['refresh_token'], result


def verify_token(tenant, oid, refresh_token):
    """Verify refresh token by exchanging for access token."""
    step("步骤 3: 验证 Token")
    print()

    rt_file = os.path.join(DATA_DIR, "rt_90day.txt")
    cache_file = os.path.join(DATA_DIR, "token_cache.json")
    os.makedirs(DATA_DIR, exist_ok=True)

    sys.path.insert(0, os.path.join(BASE_DIR, "src"))
    from m365_copilot.auth import TokenManager
    from m365_copilot.scripts.crypto import encrypt

    with open(rt_file, "w") as f:
        f.write(encrypt(refresh_token))
    print(f"  Refresh token 已加密保存")

    os.environ["M365_TENANT_ID"] = tenant
    os.environ["M365_USER_OID"] = oid

    tm = TokenManager(tenant, CLIENT_ID, SCOPE, rt_file, cache_file)
    try:
        access_token = tm.get()
        print(f"  ✓ Token 验证成功 (access_token 长度: {len(access_token)})")
    except Exception as e:
        print(f"  ✗ Token 验证失败: {e}")
        print("  可能原因: Refresh Token 已过期，请重新登录浏览器获取")
        sys.exit(1)

    return rt_file, cache_file


def save_env(tenant, oid):
    env_content = f"""# M365 Copilot Configuration
M365_TENANT_ID={tenant}
M365_USER_OID={oid}
M365_CLIENT_ID={CLIENT_ID}
"""
    with open(ENV_FILE, "w") as f:
        f.write(env_content)
    print(f"  环境变量已保存 → {ENV_FILE}")


def main():
    print("=" * 60)
    print("  M365 Copilot 配置向导 v2.0")
    print("=" * 60)
    print()

    tenant, oid, refresh_token, token_result = get_config_from_browser()
    rt_file, cache_file = verify_token(tenant, oid, refresh_token)
    save_env(tenant, oid)

    step("配置完成!")
    print()
    print("使用方式:")
    print("  m365-copilot \"你好\"              # CLI 提问")
    print("  m365-copilot -i                  # 交互模式")
    print("  m365-copilot --list-models       # 列出模型")
    print("  m365-copilot-server --port 8000  # 启动 API 服务")
    print()
    print(f"Token 存储: {DATA_DIR}")
    print(f"配置文件:   {ENV_FILE}")


if __name__ == "__main__":
    main()
