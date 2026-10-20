// Nothing mounts or requests chart data until authentication succeeds.
export async function requireSignIn() {
    const screen = document.getElementById('login-screen');
    const form = document.getElementById('login-form');
    const status = document.getElementById('login-status');
    const setup = document.getElementById('login-setup');
    const retry = document.getElementById('login-retry');
    const submit = form.querySelector('button');
    const username = form.elements.username, password = form.elements.password;
    let resolveLogin;
    const authenticated = new Promise(resolve => { resolveLogin = resolve; });
    function enter(account) {
            window.AppSession = Object.freeze(account);
            const originalFetch = window.fetch.bind(window);
            window.fetch = async (...args) => {
                const result = await originalFetch(...args);
                if (result.status === 401 && String(args[0]).startsWith('/api/') && String(args[0]) !== '/api/login') window.location.reload();
                return result;
            };
            screen.hidden = true;
            document.getElementById('app').hidden = false;
            resolveLogin(account);
    }
    async function check() {
        form.hidden = true; setup.hidden = true; retry.hidden = true;
        status.textContent = 'Connecting to the app server…';
        try {
            const response = await fetch('/api/session', {cache:'no-store'});
            if (!response.ok) throw new Error(`Account API returned HTTP ${response.status}.`);
            let account;
            try { account = await response.json(); } catch { throw new Error('The account API returned an unexpected response.'); }
            if (!['guest','user','admin'].includes(account.role) || typeof account.configured !== 'boolean') throw new Error('This server does not support account login.');
            if (!account.configured) {
                setup.hidden = false; retry.hidden = false;
                status.textContent = 'Set up your local accounts once, then choose Check again.';
                return;
            }
            // A fresh app opening must not inherit the previous person's role.
            if (account.role !== 'guest' && account.remembered) { enter(account); return; }
            if (account.role !== 'guest') {
                const logout = await fetch('/api/logout', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
                if (!logout.ok) throw new Error('Could not clear the previous account session.');
            }
            // Ask for credentials each time this page/app opens, including reload.
            form.hidden = false; username.value = account.username || '';
            status.textContent = 'Sign in to open your chart. Your account determines your permissions.';
            username.focus();
        } catch (error) {
            status.textContent = `${error.message} Restart the UI backend from your project terminal: python3 restart_ui.py. Then choose Check again.`;
            retry.hidden = false;
        }
    }
    retry.onclick = check;
    form.onsubmit = async event => {
        event.preventDefault(); submit.disabled = true; status.textContent = 'Signing in…';
        try {
            const response = await fetch('/api/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username.value,password:password.value,remember:form.elements.remember.checked})});
            const account = await response.json();
            if (!response.ok) throw new Error(account.error || 'Sign in failed');
            if (!['user','admin'].includes(account.role)) throw new Error('Unexpected account role');
            password.value = '';
            enter(account);
        } catch (error) { status.textContent = error.message; }
        finally { submit.disabled = false; }
    };
    await check();
    return authenticated;
}
