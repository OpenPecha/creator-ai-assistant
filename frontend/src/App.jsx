import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import "./App.css";

const DURATIONS = [
  { label: "30 sec", value: 30 },
  { label: "60 sec", value: 60 },
  { label: "90 sec", value: 90 },
];

const IDEA_ICONS = {
  concept: "💡",
  practice: "🧘",
  testimony: "🗣️",
  story: "📖",
  extra_info: "✨",
};

let msgId = 0;
const nextId = () => ++msgId;

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}



export default function App() {
  const [messages, setMessages] = useState([]);
  const [stage, setStage] = useState("askDay");
  const [dayInput, setDayInput] = useState("");
  const [testimonyInput, setTestimonyInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [day, setDay] = useState(null);
  const [ideaKey, setIdeaKey] = useState(null);
  const [creatorNotes, setCreatorNotes] = useState("");

  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const greeted = useRef(false);

  const addMsg = (role, content, extra = {}) =>
    setMessages((m) => [...m, { id: nextId(), role, content, ...extra }]);

  useEffect(() => {
    if (greeted.current) return;
    greeted.current = true;
    addMsg("assistant", "Hi! I'm here to help you script your next Bodhisattva Challenge video. 🙏\n\nWhich day of the plan are you filming? Just tell me the day number (1–365).");
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    if (!busy) setTimeout(() => inputRef.current?.focus(), 50);
  }, [busy, stage]);

  const fail = (err) => addMsg("assistant", `Something went wrong: ${err.message}`, { error: true });

  async function submitDay(e) {
    e?.preventDefault();
    const n = parseInt(dayInput, 10);
    if (!n || n < 1 || n > 365) {
      addMsg("assistant", "Please enter a day number between 1 and 365.");
      return;
    }
    addMsg("user", `Day ${n}`);
    setDayInput("");
    setBusy(true);
    try {
      const data = await api.getDay(n);
      setDay(data.day);
      const variantNote = data.isVariant ? " (using a draft variant)" : "";
      addMsg("assistant",
        `Here's what I found for Day ${data.day}${variantNote}.\n\nPick the type of video you want to make:`,
        { ideas: data.availableIdeas, dayMeta: { day: n, verses: data.versesLabel, date: data.date } }
      );
      setStage("askIdea");
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  function chooseIdea(idea) {
    setIdeaKey(idea.key);
    addMsg("user", idea.label);
    if (idea.key === "testimony") {
      addMsg("assistant", "Perfect. Share a few notes about your own experience with today's teaching — or leave it blank and I'll write a gentle general reflection.");
      setStage("askTestimony");
    } else {
      askDuration();
    }
  }

  function submitTestimony(e) {
    e?.preventDefault();
    setCreatorNotes(testimonyInput);
    addMsg("user", testimonyInput.trim() || "(no notes — keep it general)");
    setTestimonyInput("");
    askDuration();
  }

  function askDuration() {
    addMsg("assistant", "How long should the video be?");
    setStage("askDuration");
  }

  async function chooseDuration(seconds) {
    addMsg("user", `${seconds} seconds`);
    setBusy(true);
    setStage("generating");
    try {
      const data = await api.generateScript({ day, ideaKey, durationSeconds: seconds, creatorNotes });
      addMsg("assistant", "Here's your script:", { scriptText: data.script });
      setStage("done");
    } catch (err) {
      fail(err);
      setStage("askDuration");
    } finally {
      setBusy(false);
    }
  }

  async function makeAudio(scriptText, messageId) {
    setBusy(true);
    try {
      const data = await api.generateAudio({ script: scriptText });
      setMessages((m) => m.map((msg) => msg.id === messageId ? { ...msg, audioUrl: data.audioUrl } : msg));
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  function restart() {
    setStage("askDay");
    setDay(null);
    setIdeaKey(null);
    setCreatorNotes("");
    addMsg("assistant", "Let's make another one! Which day are you filming? (1–365)");
  }

  return (
    <div className="app">
      <header className="app__header">
        <img src="/logo.png" width="32" height="32" alt="WeBuddhist" />
        <div className="header__text">
          <h1>WeBuddhist Creator Assistant</h1>
          <p>Bodhisattva Challenge · Video script generator</p>
        </div>
      </header>

      <main className="chat" ref={scrollRef}>
        {messages.map((m) => (
          <Bubble key={m.id} msg={m} onChooseIdea={chooseIdea} onMakeAudio={makeAudio} busy={busy} />
        ))}

        {busy && (
          <div className="bubble bubble--assistant typing">
            <div className="typing-dots">
              <span /><span /><span />
            </div>
          </div>
        )}

        {!busy && stage === "askDuration" && (
          <div className="choices">
            {DURATIONS.map((d) => (
              <button key={d.value} className="chip" onClick={() => chooseDuration(d.value)}>{d.label}</button>
            ))}
          </div>
        )}

        {!busy && stage === "done" && (
          <div className="choices">
            <button className="chip chip--ghost" onClick={restart}>↻ Make another video</button>
          </div>
        )}
      </main>

      <footer className="composer">
        {stage === "askDay" && (
          <form onSubmit={submitDay} className="composer__form">
            <input
              ref={inputRef}
              type="number"
              min="1"
              max="365"
              placeholder="Enter day number (1–365)…"
              value={dayInput}
              onChange={(e) => setDayInput(e.target.value)}
              disabled={busy}
            />
            <div className="composer__actions">
              <button type="submit" className="send-btn" disabled={busy || !dayInput}>
                <SendIcon />
              </button>
            </div>
          </form>
        )}

        {stage === "askTestimony" && (
          <form onSubmit={submitTestimony} className="composer__form">
            <textarea
              ref={inputRef}
              rows={3}
              placeholder="Your experience or notes (optional)…"
              value={testimonyInput}
              onChange={(e) => setTestimonyInput(e.target.value)}
              disabled={busy}
            />
            <div className="composer__actions">
              <button type="submit" className="send-btn" disabled={busy}>
                <SendIcon />
              </button>
            </div>
          </form>
        )}

        {(stage === "askIdea" || stage === "askDuration" || stage === "generating" || stage === "done") && (
          <p className="composer__hint">
            {stage === "askIdea" && "Choose a video idea above"}
            {stage === "askDuration" && "Choose a duration above"}
            {stage === "generating" && "Generating your script…"}
            {stage === "done" && "Script ready — copy, edit, or generate audio above"}
          </p>
        )}
      </footer>
    </div>
  );
}

function Bubble({ msg, onChooseIdea, onMakeAudio, busy }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(msg.scriptText);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className={`bubble bubble--${msg.role} ${msg.error ? "bubble--error" : ""}`}>
      {msg.dayMeta && (
        <div className="day-badge">
          <div className="day-badge__item">
            <span className="day-badge__label">Day</span>
            <span className="day-badge__value">{msg.dayMeta.day}</span>
          </div>
          <div className="day-badge__divider" />
          <div className="day-badge__item">
            <span className="day-badge__label">Verses</span>
            <span className="day-badge__value">{msg.dayMeta.verses}</span>
          </div>
          <div className="day-badge__divider" />
          <div className="day-badge__item">
            <span className="day-badge__label">Date</span>
            <span className="day-badge__value">{msg.dayMeta.date}</span>
          </div>
        </div>
      )}

      <div className="bubble__text">{msg.content}</div>

      {msg.ideas && (
        <div className="ideas">
          {msg.ideas.map((idea) => (
            <button key={idea.key} className="idea-card" onClick={() => onChooseIdea(idea)} disabled={busy}>
              <span className="idea-card__icon">{IDEA_ICONS[idea.key] || "▸"}</span>
              <span className="idea-card__body">
                <span className="idea-card__label">{idea.label}</span>
                <span className="idea-card__teaser">{idea.teaser}</span>
              </span>
              <span className="idea-card__arrow">›</span>
            </button>
          ))}
        </div>
      )}

      {msg.scriptText && (
        <div className="script">
          <pre className="script__text">{msg.scriptText}</pre>
          <div className="script__actions">
            <button className="chip" onClick={copy}>{copied ? "✓ Copied" : "Copy script"}</button>
            {!msg.audioUrl && (
              <button className="chip" onClick={() => onMakeAudio(msg.scriptText, msg.id)} disabled={busy}>
                🔊 Generate audio
              </button>
            )}
          </div>
          {msg.audioUrl && (
            <div className="script__audio">
              <audio controls src={msg.audioUrl} />
              <a href={msg.audioUrl} download>↓ Download</a>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
