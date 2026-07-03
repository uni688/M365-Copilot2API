"""Conversation CRUD via REST API (cookie-based auth)."""
import json, urllib.request, ssl
from ..cookie_store import CookieStore


class ConversationAPI:
    def __init__(self, token_manager):
        self.token_manager = token_manager
        self.base_url = "https://m365.cloud.microsoft/chat"
        self.cookies = CookieStore()

    def _request(self, body=None):
        cookie_str = self.cookies.get_cookie_string()
        if not cookie_str:
            return None

        payload = json.dumps(body).encode() if body else None
        req = urllib.request.Request(self.base_url, data=payload, method='POST')
        req.add_header('Cookie', cookie_str)
        req.add_header('Content-Type', 'application/json;charset=utf-8')
        req.add_header('Accept', 'application/json')
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        req.add_header('Origin', 'https://m365.cloud.microsoft')
        req.add_header('Referer', 'https://m365.cloud.microsoft/chat')
        try:
            with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=15) as resp:
                raw = resp.read()
                ct = resp.headers.get('Content-Type', '')
                if 'json' not in ct:
                    return None
                return json.loads(raw)
        except Exception:
            return None

    def create(self):
        result = self._request({"action": "CreateConversation"})
        if result is None:
            return None
        if isinstance(result, dict) and 'error' in result:
            return None
        return result.get('conversationId')

    def delete(self, conversation_id: str):
        if not conversation_id:
            return
        self._request({
            "action": "DeleteConversation",
            "conversationId": conversation_id,
        })

    def delete_via_browser(self, conversation_id: str):
        """Delete by launching a browser with user profile and fetching the API.
        Fallback for when the REST API can't delete (blocked users)."""
        try:
            import asyncio
            from playwright.async_api import async_playwright
        except ImportError:
            return {'error': 'playwright not installed'}
        import os

        async def _delete():
            user_data = os.path.expanduser(
                '~\\AppData\\Local\\Microsoft\\Edge\\User Data')
            async with async_playwright() as p:
                ctx = await p.chromium.launch_persistent_context(
                    user_data_dir=user_data, channel='msedge',
                    headless=False,
                    args=['--disable-blink-features=AutomationControlled',
                          '--no-first-run'])
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                await page.goto('https://m365.cloud.microsoft/chat',
                                wait_until='networkidle', timeout=30000)
                await asyncio.sleep(3)

                result = await page.evaluate(f"""async () => {{
                    try {{
                        const r = await fetch('/chat', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/json'}},
                            body: JSON.stringify({{action:'DeleteConversation',
                                                   conversationId:'{conversation_id}'}})
                        }});
                        const text = await r.text();
                        try {{ return JSON.parse(text); }}
                        catch {{ return {{raw: text.substring(0,100)}}; }}
                    }} catch(e) {{ return {{error: e.toString()}}; }}
                }}""")
                await ctx.close()
                return result

        try:
            return asyncio.run(_delete())
        except Exception as e:
            return {'error': str(e)}

    def list(self):
        result = self._request({
            "action": "RefreshNavPane",
            "conversationHistoryFilter": None,
            "skipNotebooks": True,
            "skipAgentListCache": True,
        })
        if result is None:
            return []
        return (result.get('store', {})
                .get('conversationPageHistoryList', {})
                .get('chats', []))

    def delete_all(self):
        convs = self.list()
        count = len(convs)
        if count == 0:
            return 0
        deleted = 0
        for c in convs:
            self.delete(c['conversationId'])
            deleted += 1
        return deleted
