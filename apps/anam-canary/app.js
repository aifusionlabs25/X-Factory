const {AnamEvent, createClient} = window.anam;

const startButton = document.querySelector("#start");
const stopButton = document.querySelector("#stop");
const status = document.querySelector("#status");
const question = document.querySelector("#question");
const fallback = document.querySelector("#fallback");
const portrait = document.querySelector("#portrait");
const video = document.querySelector("#persona-video");
let client = null;
let config = null;
let terminal = false;

function setStatus(message, state = "working") {
  status.textContent = message;
  status.dataset.state = state;
}

async function record(event, detail = "") {
  await fetch("/api/event", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({event, detail}),
  });
}

async function loadConfig() {
  const response = await fetch("/api/config", {cache: "no-store"});
  if (!response.ok) throw new Error("Canary configuration is unavailable");
  config = await response.json();
  question.textContent = config.question;
  fallback.textContent = config.text_fallback;
  document.querySelector("#luna-budget").textContent = `${config.maximum_luna_calls} Luna calls maximum`;
  if (config.preview_mode) {
    startButton.disabled = true;
    setStatus("Local visual rehearsal. Provider controls are intentionally disabled.", "pass");
  }
}

async function startCanary() {
  startButton.disabled = true;
  setStatus("Requesting the one approved ephemeral session…");
  let connectionTimeout = null;
  try {
    const response = await fetch("/api/start", {method: "POST"});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || "Session start failed");
    if (body.spoken_text !== config.expected_spoken_text) throw new Error("Spoken text drifted from the certified fallback");
    client = createClient(body.session_token, {disableInputAudio: true});
    const connectionReady = new Promise((resolve, reject) => {
      client.addListener(AnamEvent.CONNECTION_ESTABLISHED, async () => {
        await record("CONNECTION_ESTABLISHED");
        resolve();
      });
      client.addListener(AnamEvent.CONNECTION_CLOSED, async (code) => {
        await record("CONNECTION_CLOSED", String(code));
        reject(new Error(`ANAM connection closed before readiness (${code})`));
      });
      connectionTimeout = window.setTimeout(
        () => reject(new Error("ANAM connection readiness timed out")),
        30000,
      );
    });
    await client.streamToVideoElement("persona-video");
    await connectionReady;
    window.clearTimeout(connectionTimeout);
    if (!client.isStreaming()) throw new Error("ANAM reported readiness without an active stream");
    portrait.hidden = true;
    video.classList.add("active");
    stopButton.disabled = false;
    setStatus("Mia is connected. Sending the exact certified Luna response…");
    await client.talk(body.spoken_text);
    await record("TALK_COMMAND_ACCEPTED", body.spoken_text);
    setStatus("Canary passed: Mia received the exact text shown above.", "pass");
  } catch (error) {
    window.clearTimeout(connectionTimeout);
    terminal = true;
    try {
      if (client?.isStreaming()) await client.stopStreaming();
    } catch {
      // The failure record below remains authoritative even if teardown is already complete.
    }
    await record("CANARY_FAILED", String(error.message || error));
    setStatus(`Canary stopped safely: ${error.message || error}`, "fail");
    stopButton.disabled = true;
  }
}

async function stopCanary() {
  if (terminal) return;
  stopButton.disabled = true;
  if (client) await client.stopStreaming();
  await record("SESSION_STOPPED_BY_USER");
  setStatus("Contained session ended. No deployment or provider mutation occurred.", "pass");
}

startButton.addEventListener("click", startCanary, {once: true});
stopButton.addEventListener("click", stopCanary);
loadConfig().catch((error) => {
  setStatus(error.message, "fail");
  startButton.disabled = true;
});
