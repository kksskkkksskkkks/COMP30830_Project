const API_BASE = `http://${window.location.hostname}:5000/auth`;

document.addEventListener('DOMContentLoaded', () => {
    // Login Handling
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.onsubmit = async (e) => {
            e.preventDefault();
            try {
                const res = await fetch(`${API_BASE}/login`, {
                    method: 'POST', body: new FormData(e.target), credentials: 'include'
                });
                if (!res.ok) {
                    const data = await res.json();
                    throw new Error(data.error);
                }
                window.location.href = 'index.html';
            } catch (err) {
                alert(err.message);
            }
        };
    }

    // Register Handling
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.onsubmit = async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button');
            btn.disabled = true;
            document.getElementById('btn-spinner').classList.remove('hidden');
            try {
                const res = await fetch(`${API_BASE}/register`, {
                    method: 'POST', body: new FormData(e.target), credentials: 'include'
                });
                if (res.status === 201) {
                    document.getElementById('success-overlay').classList.remove('hidden');
                    setTimeout(() => { window.location.href = 'login.html'; }, 1200);
                } else {
                    const data = await res.json();
                    throw new Error(data.error);
                }
            } catch (err) {
                alert(err.message);
                btn.disabled = false;
                document.getElementById('btn-spinner').classList.add('hidden');
            }
        };
    }

    // Logout Handling
    const logoutProcessing = document.getElementById('logout-processing');
    if (logoutProcessing) {
        performLogout();
    }
});

async function performLogout() {
    try {
        const res = await fetch(`${API_BASE}/logout`, {
            method: 'GET',
            credentials: 'include'
        });

        if (res.ok) {
            document.getElementById('logout-processing').classList.add('hidden');
            document.getElementById('logout-success').classList.remove('hidden');
            setTimeout(() => {
                window.location.href = 'index.html';
            }, 2000);
        } else {
            window.location.href = 'index.html';
        }
    } catch (err) {
        console.error("Logout process failed:", err);
        window.location.href = 'index.html';
    }
}
