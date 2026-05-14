const state = {
  token: localStorage.getItem("token") || "",
  user: null,
  users: [],
  channels: [],
  messages: [],
  integrations: [],
  selectedChannelId: null,
  notice: "",
  error: "",
};

const app = document.querySelector("#app");

function headers() {
  const base = { "Content-Type": "application/json" };
  if (state.token) base.Authorization = `Bearer ${state.token}`;
  return base;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: headers(),
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || "Request failed");
  }
  return data;
}

function setNotice(message) {
  state.notice = message;
  state.error = "";
  render();
}

function setError(message) {
  state.error = message;
  state.notice = "";
  render();
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function bootstrap() {
  if (!state.token) {
    render();
    return;
  }
  try {
    const me = await api("/api/auth/me");
    state.user = me.user;
    await refreshWorkspace();
  } catch (error) {
    localStorage.removeItem("token");
    state.token = "";
    state.user = null;
    setError(error.message);
  }
}

async function refreshWorkspace() {
  const channelData = await api("/api/channels");
  state.channels = channelData.channels;
  if (!state.selectedChannelId && state.channels.length) {
    state.selectedChannelId = state.channels[0].id;
  }
  if (state.selectedChannelId) {
    const messageData = await api(`/api/channels/${state.selectedChannelId}/messages`);
    state.messages = messageData.messages;
  }
  if (["admin", "moderator"].includes(state.user.role)) {
    const integrationData = await api("/api/integrations");
    state.integrations = integrationData.integrations;
  }
  if (state.user.role === "admin") {
    const userData = await api("/api/users");
    state.users = userData.users;
  }
  render();
}

function render() {
  app.innerHTML = state.user ? workspaceView() : authView();
  bindEvents();
}

function flash() {
  if (state.error) return `<div class="notice error">${esc(state.error)}</div>`;
  if (state.notice) return `<div class="notice">${esc(state.notice)}</div>`;
  return "";
}

function authView() {
  return `
    <section class="auth-layout">
      <div class="auth-panel">
        <div class="brand"><span class="brand-mark">CL</span><span>CorpLink</span></div>
        <h1>Корпоративный мессенджер с каналами и интеграциями</h1>
        <p>Рабочее пространство для командных каналов, сообщений, webhook-интеграций, аудита и ролевого доступа.</p>
      </div>
      <form class="auth-form" data-action="login">
        <div class="panel">
          <h2>Вход</h2>
          ${flash()}
          <label>Email
            <input name="email" type="email" value="admin@corp.test" autocomplete="username" required>
          </label>
          <label>Пароль
            <input name="password" type="password" value="AdminPass123" autocomplete="current-password" required>
          </label>
          <div class="toolbar">
            <button type="submit">Войти</button>
            <button class="secondary" type="button" data-action="seed">Seed</button>
          </div>
        </div>
      </form>
    </section>
  `;
}

function workspaceView() {
  return `
    <header class="topbar">
      <div class="brand"><span class="brand-mark">CL</span><span>CorpLink</span></div>
      <div class="session">
        <span>${esc(state.user.name)} · ${esc(state.user.role)}</span>
        <button class="secondary" data-action="logout">Выйти</button>
      </div>
    </header>
    <section class="workspace">
      <aside class="section">
        <div class="section-header">
          <h2>Каналы</h2>
          <button class="ghost" data-action="reload">Обновить</button>
        </div>
        ${flash()}
        <div class="list">${state.channels.map(channelItem).join("")}</div>
        ${staffOnly(channelForm())}
      </aside>
      <main class="section">
        ${messageColumn()}
      </main>
      <aside class="section side-column">
        ${staffOnly(integrationPanel())}
        ${adminOnly(usersPanel())}
      </aside>
    </section>
  `;
}

function channelItem(channel) {
  const active = channel.id === state.selectedChannelId ? " active" : "";
  const badge = channel.is_private ? `<span class="badge private">private</span>` : `<span class="badge">open</span>`;
  return `
    <button class="list-item${active}" data-action="select-channel" data-id="${channel.id}">
      <span class="list-title">#${esc(channel.slug)} ${badge}</span>
      <span class="list-meta">${esc(channel.description)}</span>
    </button>
  `;
}

function channelForm() {
  return `
    <form class="panel channel-form" data-action="create-channel">
      <div class="section-header"><h3>Новый канал</h3></div>
      <input name="slug" placeholder="release-room" required>
      <input name="name" placeholder="Release Room" required>
      <textarea name="description" placeholder="Назначение канала" required></textarea>
      <label><input name="is_private" type="checkbox"> Приватный канал</label>
      <button type="submit">Создать</button>
    </form>
  `;
}

function selectedChannel() {
  return state.channels.find((channel) => channel.id === state.selectedChannelId);
}

function messageColumn() {
  const channel = selectedChannel();
  if (!channel) {
    return `<div class="panel panel-pad muted">Нет доступных каналов</div>`;
  }
  return `
    <div class="section-header">
      <div>
        <h2>#${esc(channel.slug)}</h2>
        <div class="muted">${esc(channel.name)} · ${esc(channel.description)}</div>
      </div>
      ${staffOnly(`<button class="danger" data-action="delete-channel" data-id="${channel.id}">Удалить</button>`)}
    </div>
    <div class="messages">
      ${state.messages.map(messageItem).join("") || `<div class="panel panel-pad muted">Сообщений пока нет</div>`}
    </div>
    <form class="panel compose" data-action="send-message">
      <textarea name="body" placeholder="Сообщение" required></textarea>
      <button type="submit">Отправить</button>
    </form>
  `;
}

function messageItem(message) {
  const canEdit = message.author_id === state.user.id || ["admin", "moderator"].includes(state.user.role);
  return `
    <article class="message">
      <div class="message-head">
        <strong>${esc(message.author_name)}</strong>
        <span>${esc(message.created_at)}${message.edited ? " · edited" : ""}</span>
      </div>
      <div class="message-body">${esc(message.body)}</div>
      ${canEdit ? `<div class="toolbar"><button class="ghost" data-action="delete-message" data-id="${message.id}">Удалить</button></div>` : ""}
    </article>
  `;
}

function integrationPanel() {
  return `
    <div class="panel">
      <form class="integration-form" data-action="create-integration">
        <div class="section-header"><h3>Интеграции</h3></div>
        <select name="channel_id">${state.channels.map((channel) => `<option value="${channel.id}">#${esc(channel.slug)}</option>`).join("")}</select>
        <input name="name" placeholder="CI notifier" required>
        <select name="type">
          <option value="webhook">webhook</option>
          <option value="git">git</option>
          <option value="ci">ci</option>
          <option value="calendar">calendar</option>
        </select>
        <textarea name="config" placeholder='{"url":"https://example.test/hook"}'>{}</textarea>
        <button type="submit">Добавить</button>
      </form>
      <div class="panel-pad">
        <table class="table">
          <thead><tr><th>Название</th><th>Тип</th><th></th></tr></thead>
          <tbody>${state.integrations.map(integrationRow).join("")}</tbody>
        </table>
      </div>
    </div>
  `;
}

function integrationRow(integration) {
  return `
    <tr>
      <td>${esc(integration.name)}</td>
      <td>${esc(integration.type)}</td>
      <td><button class="ghost" data-action="delete-integration" data-id="${integration.id}">Удалить</button></td>
    </tr>
  `;
}

function usersPanel() {
  return `
    <div class="panel">
      <form class="admin-form" data-action="create-user">
        <div class="section-header"><h3>Пользователи</h3></div>
        <div class="grid-2">
          <input name="email" type="email" placeholder="user@corp.test" required>
          <input name="name" placeholder="Name" required>
        </div>
        <div class="grid-2">
          <input name="password" type="password" placeholder="Password123" required>
          <select name="role">
            <option value="member">member</option>
            <option value="moderator">moderator</option>
            <option value="admin">admin</option>
            <option value="bot">bot</option>
          </select>
        </div>
        <button type="submit">Создать пользователя</button>
      </form>
      <div class="panel-pad">
        <table class="table">
          <thead><tr><th>Email</th><th>Роль</th><th>Статус</th></tr></thead>
          <tbody>${state.users.map(userRow).join("")}</tbody>
        </table>
      </div>
    </div>
  `;
}

function userRow(user) {
  return `
    <tr>
      <td>${esc(user.email)}</td>
      <td>${esc(user.role)}</td>
      <td>${user.active ? "active" : "disabled"}</td>
    </tr>
  `;
}

function staffOnly(html) {
  return state.user && ["admin", "moderator"].includes(state.user.role) ? html : "";
}

function adminOnly(html) {
  return state.user && state.user.role === "admin" ? html : "";
}

function bindEvents() {
  document.querySelectorAll("[data-action]").forEach((node) => {
    const action = node.dataset.action;
    if (node.tagName === "FORM") {
      node.addEventListener("submit", (event) => onSubmit(event, action));
    } else {
      node.addEventListener("click", () => onClick(action, node));
    }
  });
}

async function onClick(action, node) {
  try {
    if (action === "seed") {
      await api("/api/seed", { method: "POST" });
      setNotice("Тестовые данные созданы");
    }
    if (action === "logout") {
      localStorage.removeItem("token");
      state.token = "";
      state.user = null;
      render();
    }
    if (action === "reload") {
      await refreshWorkspace();
      setNotice("Данные обновлены");
    }
    if (action === "select-channel") {
      state.selectedChannelId = Number(node.dataset.id);
      const messageData = await api(`/api/channels/${state.selectedChannelId}/messages`);
      state.messages = messageData.messages;
      render();
    }
    if (action === "delete-channel") {
      await api(`/api/channels/${node.dataset.id}`, { method: "DELETE" });
      state.selectedChannelId = null;
      await refreshWorkspace();
    }
    if (action === "delete-message") {
      await api(`/api/messages/${node.dataset.id}`, { method: "DELETE" });
      await refreshWorkspace();
    }
    if (action === "delete-integration") {
      await api(`/api/integrations/${node.dataset.id}`, { method: "DELETE" });
      await refreshWorkspace();
    }
  } catch (error) {
    setError(error.message);
  }
}

async function onSubmit(event, action) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form).entries());
  try {
    if (action === "login") {
      const session = await api("/api/auth/login", { method: "POST", body: data });
      state.token = session.token;
      state.user = session.user;
      localStorage.setItem("token", state.token);
      await refreshWorkspace();
    }
    if (action === "create-channel") {
      data.is_private = form.elements.is_private.checked;
      await api("/api/channels", { method: "POST", body: data });
      form.reset();
      await refreshWorkspace();
    }
    if (action === "send-message") {
      await api(`/api/channels/${state.selectedChannelId}/messages`, { method: "POST", body: data });
      form.reset();
      await refreshWorkspace();
    }
    if (action === "create-integration") {
      data.channel_id = Number(data.channel_id);
      data.config = JSON.parse(data.config || "{}");
      data.enabled = true;
      await api("/api/integrations", { method: "POST", body: data });
      form.reset();
      await refreshWorkspace();
    }
    if (action === "create-user") {
      await api("/api/users", { method: "POST", body: data });
      form.reset();
      await refreshWorkspace();
    }
  } catch (error) {
    setError(error.message);
  }
}

bootstrap();
