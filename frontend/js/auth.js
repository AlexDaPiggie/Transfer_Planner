import { API_BASE } from "./config.js";
const apiBase = `${API_BASE}/api/auth`;
const controls = document.querySelector("#auth-controls");
const dialog = document.querySelector("#auth-dialog");
const form = document.querySelector("#auth-form");
const subtitle = document.querySelector("#auth-subtitle");
const formSubmit = document.querySelector("#auth-submit");
const toggle = document.querySelector("#auth-toggle");
const message = document.querySelector("#auth-message");
const googleArea = document.querySelector("#google-signin");
const forgot = document.querySelector("#auth-forgot");
let recoveryAvailable = false;
let recoveryToken = "";
let mode = "login";
let googleReady = false;
let googleScriptPromise = null;

async function authRequest(path, method = "GET", body = null) {
  const response = await fetch(`${apiBase}/${path}`, {
    method, credentials: "include",
    headers: {
      ...(body === null ? {} : {"Content-Type": "application/json"}),
      "X-Pathway-Request": "1",
    },
    ...(body === null ? {} : {body: JSON.stringify(body)}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? "Please check your email and password." : data.detail;
    throw new Error(detail || "Authentication failed. Please try again.");
  }
  return data;
}

function drawControls(user) {
  window.dispatchEvent(new CustomEvent("pathway:auth-changed", { detail: { user } }));
  controls.replaceChildren();
  if (!user) {
    const signIn = document.createElement("button");
    signIn.type = "button";
    signIn.className = "auth-button";
    signIn.textContent = "Log in / Sign up";
    signIn.addEventListener("click", openDialog);
    controls.append(signIn);
    return;
  }
  const email = document.createElement("span");
  email.className = "auth-email";
  email.textContent = user.email;
  const logout = document.createElement("button");
  logout.type = "button";
  logout.className = "auth-button";
  logout.textContent = "Log out";
  logout.addEventListener("click", async () => {
    try {
      await authRequest("logout", "POST");
      window.google?.accounts?.id?.disableAutoSelect();
      drawControls(null);
    } catch (error) { window.alert(error.message); }
  });
  controls.append(email, logout);
}

function setMode(next) {
  mode = next;
  const titles = { login: "Welcome back to Pathway", signup: "Create your Pathway account", forgot: "Recover your account", reset: "Choose a new password" };
  const actions = { login: "Log in", signup: "Create account", forgot: "Send recovery link", reset: "Save new password" };
  formSubmit.textContent = actions[mode];
  subtitle.textContent = titles[mode];
  toggle.textContent = mode === "login" ? "Need an account? Sign up" : "Already have an account? Log in";
  const emailHidden = mode === "reset", passwordHidden = mode === "forgot";
  form.elements.email.disabled = emailHidden;
  form.elements.email.hidden = emailHidden;
  document.querySelector('label[for="auth-email"]').hidden = emailHidden;
  form.elements.password.disabled = passwordHidden;
  form.elements.password.hidden = passwordHidden;
  form.elements.password.minLength = ["signup", "reset"].includes(mode) ? 10 : 1;
  form.elements.password.autocomplete = mode === "login" ? "current-password" : "new-password";
  document.querySelector('label[for="auth-password"]').hidden = passwordHidden;
  googleArea.hidden = ["forgot", "reset"].includes(mode);
  document.querySelector(".auth-divider").hidden = googleArea.hidden;
  forgot.hidden = mode !== "login" || !recoveryAvailable;
  message.textContent = "";
}

function googleScript() {
  if (window.google?.accounts?.id) return Promise.resolve();
  if (!googleScriptPromise) {
    googleScriptPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://accounts.google.com/gsi/client";
      s.async = true;
      s.onload = resolve;
      s.onerror = () => reject(new Error("Could not load Google Sign-In."));
      document.head.append(s);
    });
  }
  return googleScriptPromise;
}

async function showGoogleButton() {
  googleArea.textContent = "";
  try {
    const cfg = await authRequest("config");
    recoveryAvailable = cfg.password_reset_available;
    forgot.hidden = mode !== "login" || !recoveryAvailable;
    if (!cfg.google_client_id) {
      googleArea.textContent = "Google sign-in has not been configured yet.";
      return;
    }
    await googleScript();
    if (!googleReady) {
      window.google.accounts.id.initialize({
        client_id: cfg.google_client_id,
        auto_select: false,
        callback: async (result) => {
          try {
            const response = await authRequest("google", "POST", {credential: result.credential});
            drawControls(response.user);
            dialog.close();
          } catch (error) { message.textContent = error.message; }
        },
      });
      googleReady = true;
    }
    window.google.accounts.id.renderButton(googleArea, {
      theme: "outline", size: "large", text: "continue_with", width: 280,
    });
  } catch (error) { googleArea.textContent = error.message; }
}

function openDialog() {
  form.reset();
  setMode("login");
  dialog.showModal();
  showGoogleButton();
}

document.querySelector("#auth-close").addEventListener("click", () => dialog.close());
toggle.addEventListener("click", () => { setMode(mode === "login" ? "signup" : "login"); showGoogleButton(); });
forgot.addEventListener("click", () => setMode("forgot"));
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  message.textContent = "";
  formSubmit.disabled = true;
  try {
    if (mode === "forgot") {
      const result = await authRequest("forgot-password", "POST", { email: form.elements.email.value });
      message.textContent = result.message;
      return;
    }
    if (mode === "reset") {
      const result = await authRequest("reset-password", "POST", { token: recoveryToken, password: form.elements.password.value });
      recoveryToken = ""; form.reset(); setMode("login"); drawControls(null);
      message.textContent = result.message;
      return;
    }
    const response = await authRequest(mode, "POST", {
      email: form.elements.email.value,
      password: form.elements.password.value,
    });
    drawControls(response.user);
    dialog.close();
  } catch (error) { message.textContent = error.message; }
  finally { formSubmit.disabled = false; }
});

authRequest("me")
  .then((result) => drawControls(result.logged_in ? result.user : null))
  .catch(() => drawControls(null));

const action = new URLSearchParams(window.location.hash.slice(1));
if (action.has("reset")) {
  recoveryToken = action.get("reset");
  history.replaceState(null, "", location.pathname + location.search);
  setMode("reset");
  dialog.showModal();
}
