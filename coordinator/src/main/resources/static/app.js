const authView = document.getElementById("authView");
const adminView = document.getElementById("adminView");
const chatView = document.getElementById("chatView");
const loginTab = document.getElementById("loginTab");
const registerTab = document.getElementById("registerTab");
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");
const loginMessage = document.getElementById("loginMessage");
const registerMessage = document.getElementById("registerMessage");
const backToChatButton = document.getElementById("backToChatButton");
const adminChatButton = document.getElementById("adminChatButton");
const adminLogoutButton = document.getElementById("adminLogoutButton");
const chatDashboardButton = document.getElementById("chatDashboardButton");
const chatLoginButton = document.getElementById("chatLoginButton");
const chatSignupButton = document.getElementById("chatSignupButton");
const userLogoutButton = document.getElementById("userLogoutButton");
const registeredUserCount = document.getElementById("registeredUserCount");
const adminUsername = document.getElementById("adminUsername");
const dishForm = document.getElementById("dishForm");
const dishMessage = document.getElementById("dishMessage");
const dishList = document.getElementById("dishList");
const userGreeting = document.getElementById("userGreeting");
const chat = document.getElementById("chat");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");

const COORDINATOR_BASE_URL = "";
const SESSION_STORAGE_KEY = "food-ai-session";
const POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 30;
const PROCESSING_STATES = new Set(["received", "formatted", "unformatted result"]);

let currentUser = null;

document.addEventListener("DOMContentLoaded", initializeApp);

async function initializeApp() {
    bindEvents();

    const sessionUser = getSessionUser();

    if (sessionUser) {
        signIn(sessionUser);
    } else {
        showChat(null);
    }
}

function bindEvents() {
    loginTab.addEventListener("click", () => showAuthTab("login"));
    registerTab.addEventListener("click", () => showAuthTab("register"));
    backToChatButton.addEventListener("click", () => showChat(currentUser));
    loginForm.addEventListener("submit", handleLogin);
    registerForm.addEventListener("submit", handleRegister);
    dishForm.addEventListener("submit", handleDishSubmit);
    adminChatButton.addEventListener("click", () => showChat(currentUser));
    chatDashboardButton.addEventListener("click", () => showAdminDashboard(currentUser));
    chatLoginButton.addEventListener("click", () => showAuth("login"));
    chatSignupButton.addEventListener("click", () => showAuth("register"));
    adminLogoutButton.addEventListener("click", logout);
    userLogoutButton.addEventListener("click", logout);
    chatForm.addEventListener("submit", handleChatSubmit);

    messageInput.addEventListener("input", function () {
        messageInput.style.height = "auto";
        messageInput.style.height = messageInput.scrollHeight + "px";
    });

    messageInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            chatForm.requestSubmit();
        }
    });
}

function getSessionUser() {
    try {
        return JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY));
    } catch {
        return null;
    }
}

async function handleLogin(event) {
    event.preventDefault();
    loginMessage.textContent = "";

    const username = document.getElementById("loginUsername").value.trim();
    const password = document.getElementById("loginPassword").value;

    try {
        const user = await postJson("/api/login", { username, password });
        signIn(user);
    } catch (error) {
        loginMessage.textContent = error.message || "Username or password is incorrect.";
    }
}

async function handleRegister(event) {
    event.preventDefault();
    registerMessage.textContent = "";

    const username = document.getElementById("registerUsername").value.trim();
    const password = document.getElementById("registerPassword").value;
    const likes = splitList(document.getElementById("registerLikes").value);
    const allergies = splitList(document.getElementById("registerAllergies").value);
    const diet = document.getElementById("registerDiet").value;

    if (username.length < 3) {
        registerMessage.textContent = "Username must be at least 3 characters.";
        return;
    }

    if (password.length < 4) {
        registerMessage.textContent = "Password must be at least 4 characters.";
        return;
    }

    try {
        const newUser = await postJson("/api/register", {
            username,
            password,
            likes,
            allergies,
            diet
        });
        registerForm.reset();
        signIn(newUser);
    } catch (error) {
        registerMessage.textContent = error.message || "Could not create account.";
    }
}

function splitList(value) {
    return value
        .split(",")
        .map(item => item.trim())
        .filter(Boolean);
}

async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    return await parseJsonResponse(response);
}

async function postJson(url, body) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(body)
    });

    return await parseJsonResponse(response);
}

async function parseJsonResponse(response) {
    const text = await response.text();
    const data = text ? JSON.parse(text) : null;

    if (!response.ok) {
        throw new Error(data?.message || data?.error || "Request failed.");
    }

    return data;
}

function signIn(user) {
    currentUser = user;
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(user));
    showChat(user);
}

function logout() {
    currentUser = null;
    localStorage.removeItem(SESSION_STORAGE_KEY);
    showChat(null);
}

function showAuth(tab = "login") {
    authView.classList.remove("hidden");
    adminView.classList.add("hidden");
    chatView.classList.add("hidden");
    showAuthTab(tab);
}

function showAuthTab(tab) {
    const isLogin = tab === "login";

    loginTab.classList.toggle("active", isLogin);
    registerTab.classList.toggle("active", !isLogin);
    loginForm.classList.toggle("hidden", !isLogin);
    registerForm.classList.toggle("hidden", isLogin);
    loginMessage.textContent = "";
    registerMessage.textContent = "";
}

async function showAdminDashboard(user) {
    if (!user || !user.isAdmin) {
        showChat(user);
        return;
    }

    authView.classList.add("hidden");
    adminView.classList.remove("hidden");
    chatView.classList.add("hidden");

    adminUsername.textContent = user.username;
    registeredUserCount.textContent = "...";

    try {
        const users = await fetchJson("/api/users");
        registeredUserCount.textContent = String(users.filter(account => !account.isAdmin).length);
    } catch (error) {
        registeredUserCount.textContent = "0";
    }

    loadDishes();
}

async function handleDishSubmit(event) {
    event.preventDefault();
    dishMessage.textContent = "";

    const name = document.getElementById("dishName").value.trim();
    const ingredients = splitList(document.getElementById("dishIngredients").value);
    const cookingMethod = document.getElementById("dishCookingMethod").value.trim();

    if (!name || ingredients.length === 0 || !cookingMethod) {
        dishMessage.textContent = "Dish name, ingredients, and cooking method are required.";
        return;
    }

    try {
        await postJson("/api/dishes", {
            name,
            ingredients,
            cookingMethod
        });
        dishForm.reset();
        dishMessage.textContent = "Dish saved.";
        dishMessage.classList.add("success");
        await loadDishes();
    } catch (error) {
        dishMessage.classList.remove("success");
        dishMessage.textContent = error.message || "Could not save dish.";
    }
}

async function loadDishes() {
    dishList.innerHTML = "<p class=\"muted\">Loading dishes...</p>";

    try {
        const dishes = await fetchJson("/api/dishes");
        renderDishes(dishes);
    } catch (error) {
        dishList.innerHTML = "<p class=\"form-message\">Could not load dishes.</p>";
    }
}

function renderDishes(dishes) {
    dishList.innerHTML = "";

    if (!Array.isArray(dishes) || dishes.length === 0) {
        dishList.innerHTML = "<p class=\"muted\">No dishes saved yet.</p>";
        return;
    }

    dishes.forEach(dish => {
        const item = document.createElement("article");
        item.classList.add("dish-item");

        const title = document.createElement("h4");
        title.textContent = dish.name;

        const ingredients = document.createElement("p");
        ingredients.innerHTML = `<strong>Ingredients:</strong> ${formatList(dish.ingredients)}`;

        const cookingMethod = document.createElement("p");
        cookingMethod.innerHTML = `<strong>Way to cook:</strong> ${dish.cookingMethod || "none"}`;

        item.appendChild(title);
        item.appendChild(ingredients);
        item.appendChild(cookingMethod);
        dishList.appendChild(item);
    });
}

function showChat(user) {
    authView.classList.add("hidden");
    adminView.classList.add("hidden");
    chatView.classList.remove("hidden");

    userGreeting.textContent = user ? `Welcome, ${user.username}` : "Food AI Assistant";
    chatDashboardButton.classList.toggle("hidden", !user?.isAdmin);
    chatLoginButton.classList.toggle("hidden", Boolean(user));
    chatSignupButton.classList.toggle("hidden", Boolean(user));
    userLogoutButton.classList.toggle("hidden", !user);
}

function formatList(value) {
    return Array.isArray(value) && value.length > 0 ? value.join(", ") : "none";
}

function addMessage(role, text, results = []) {
    const message = document.createElement("div");
    message.classList.add("message");

    if (role === "user") {
        message.classList.add("user-message");
    } else {
        message.classList.add("assistant-message");
    }

    const avatar = document.createElement("div");
    avatar.classList.add("avatar");
    avatar.textContent = role === "user" ? "U" : "AI";

    const bubble = document.createElement("div");
    bubble.classList.add("bubble");
    bubble.textContent = text;

    results.forEach(result => {
        bubble.appendChild(createResultCard(result));
    });

    message.appendChild(avatar);
    message.appendChild(bubble);
    chat.appendChild(message);
    scrollToBottom();
}

function createResultCard(result) {
    const card = document.createElement("div");
    card.classList.add("result-card");

    const dishName = result.dish || result.dishName || result.name || "Unknown Dish";
    const matchScore = result.matchScore || 0;
    const missingIngredients = result.missingIngredients || [];

    const title = document.createElement("div");
    title.classList.add("result-title");
    title.textContent = dishName;

    const missing = document.createElement("div");
    missing.classList.add("result-info");
    missing.innerHTML = `<strong>Missing ingredients:</strong> ${formatList(missingIngredients)}`;

    const match = document.createElement("div");
    match.classList.add("match-pill");
    match.textContent = `Match ${Math.round(matchScore * 100)}%`;

    card.appendChild(title);
    card.appendChild(missing);
    card.appendChild(match);

    return card;
}

function addTypingMessage() {
    const message = document.createElement("div");
    message.classList.add("message", "assistant-message");
    message.id = "typingMessage";

    const avatar = document.createElement("div");
    avatar.classList.add("avatar");
    avatar.textContent = "AI";

    const bubble = document.createElement("div");
    bubble.classList.add("bubble", "typing");
    bubble.textContent = "Thinking...";

    message.appendChild(avatar);
    message.appendChild(bubble);
    chat.appendChild(message);
    scrollToBottom();
}

function removeTypingMessage() {
    const typingMessage = document.getElementById("typingMessage");

    if (typingMessage) {
        typingMessage.remove();
    }
}

function scrollToBottom() {
    window.scrollTo({
        top: document.body.scrollHeight,
        behavior: "smooth"
    });
}

async function callCoordinatorSearch(userMessage) {
    const response = await fetch(`${COORDINATOR_BASE_URL}/search`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            userQuery: userMessage
        })
    });

    if (!response.ok) {
        throw new Error(`Coordinator returned ${response.status}`);
    }

    const requestId = (await response.text()).trim();
    const result = await pollCoordinatorResult(requestId);

    return {
        reply: result,
        results: []
    };
}

async function pollCoordinatorResult(requestId) {
    for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
        const response = await fetch(
            `${COORDINATOR_BASE_URL}/get?id=${encodeURIComponent(requestId)}`
        );

        if (!response.ok) {
            throw new Error(`Coordinator returned ${response.status}`);
        }

        const text = (await response.text()).trim();

        if (!PROCESSING_STATES.has(text)) {
            return text;
        }

        await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
    }

    return "The request is still processing. Try again in a moment.";
}

async function getAssistantResponse(userMessage) {
    return await callCoordinatorSearch(userMessage);
}

async function handleChatSubmit(event) {
    event.preventDefault();

    const messageText = messageInput.value.trim();

    if (!messageText) {
        return;
    }

    messageInput.value = "";
    messageInput.style.height = "auto";

    addMessage("user", messageText);
    addTypingMessage();
    sendButton.disabled = true;

    try {
        const data = await getAssistantResponse(messageText);
        removeTypingMessage();
        addMessage("assistant", data.reply || "I found some results.", data.results || []);
    } catch (error) {
        removeTypingMessage();
        addMessage(
            "assistant",
            "I could not connect to the Coordinator. Make sure the Coordinator is running on port 8080."
        );
        console.error(error);
    } finally {
        sendButton.disabled = false;
    }
}