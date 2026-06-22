import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import "./App.css";

const DURATIONS = [
  { label: "30 sec", value: 30 },
  { label: "45 sec", value: 45 },
  { label: "60 sec", value: 60 },
  { label: "90 sec", value: 90 },
];

const OUTPUT_TYPES = [
  { key: "script", label: "Video script", desc: "A ready-to-read spoken script." },
  { key: "structure", label: "Video structure", desc: "A shot-by-shot plan: timed beats, on-screen visuals, and voiceover." },
];

const LANGUAGES = [
  { key: "english", label: "English" },
  { key: "hindi", label: "हिन्दी Hindi" },
];

const IDEA_ICONS = {
  concept: "💡",
  practice: "🧘",
  creative: "🎨",
  testimony: "🗣️",
  story: "📖",
  extra_info: "✨",
};

let msgId = 0;
const nextId = () => ++msgId;

// Extract the chapter number from a verse label like "1.6–1.8" or "Prologue, 1.1–1.3".
const chapterFrom = (label) => {
  const m = String(label || "").match(/(\d+)\.\d+/);
  return m ? m[1] : "—";
};

// Strip the chapter prefix so "1.15–1.16" shows as "15–16".
const versesOnly = (label) =>
  String(label || "").replace(/(\d+)\.(\d+)/g, "$2");

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
  const [pendingIdeas, setPendingIdeas] = useState(null);
  const [otherLang, setOtherLang] = useState(null);
  const [outputType, setOutputType] = useState("script");
  const [duration, setDuration] = useState(null);
  const [lastOutput, setLastOutput] = useState(null);
  const [refineInput, setRefineInput] = useState("");

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
      setPendingIdeas(data.availableIdeas);
      const variantNote = data.isVariant ? " (using a draft variant)" : "";
      addMsg("assistant",
        `Here's what I found for Day ${data.day}${variantNote}. Today's verses:`,
        {
          dayMeta: { day: n, chapter: chapterFrom(data.versesLabel), verses: versesOnly(data.versesLabel), date: data.date },
          verseText: data.verseText,
        }
      );
      addMsg("assistant", "Want a quick, simple breakdown of today's verses? Pick a language:");
      setStage("askLanguage");
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }

  const langName = (key) => (key === "hindi" ? "Hindi" : "English");

  function showIdeas() {
    addMsg("assistant", "Now, pick the type of video you want to make:", { ideas: pendingIdeas });
    setStage("askIdea");
  }

  async function chooseLanguage(lang) {
    const label = LANGUAGES.find((l) => l.key === lang)?.label || lang;
    addMsg("user", label);
    setBusy(true);
    setStage("summarizing");
    try {
      const data = await api.verseSummary({ day, language: lang });
      addMsg("assistant", "Here's a simple breakdown of today's verses:", { summaryPoints: data.points });
      const other = lang === "hindi" ? "english" : "hindi";
      setOtherLang(other);
      addMsg("assistant", `Would you like this in ${langName(other)} as well?`);
      setStage("askOtherLanguage");
    } catch (err) {
      fail(err);
      setStage("askLanguage");
    } finally {
      setBusy(false);
    }
  }

  async function chooseOtherLanguage(wantsIt) {
    if (!wantsIt) {
      addMsg("user", "No, continue");
      showIdeas();
      return;
    }
    addMsg("user", `Yes, in ${langName(otherLang)} too`);
    setBusy(true);
    setStage("summarizing");
    try {
      const data = await api.verseSummary({ day, language: otherLang });
      addMsg("assistant", `Here it is in ${langName(otherLang)}:`, { summaryPoints: data.points });
      showIdeas();
    } catch (err) {
      fail(err);
      setStage("askOtherLanguage");
    } finally {
      setBusy(false);
    }
  }

  function chooseIdea(idea) {
    setIdeaKey(idea.key);
    addMsg("user", idea.label);
    addMsg("assistant", "How would you like it?");
    setStage("askOutputType");
  }

  function chooseOutputType(type) {
    setOutputType(type);
    addMsg("user", OUTPUT_TYPES.find((o) => o.key === type)?.label || type);
    if (ideaKey === "testimony") {
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

  async function generate({ seconds, feedback = "", previous = null, onErrorStage }) {
    setBusy(true);
    setStage("generating");
    try {
      if (outputType === "structure") {
        const payload = { day, ideaKey, durationSeconds: seconds, creatorNotes };
        if (feedback) { payload.feedback = feedback; payload.previous = previous; }
        const data = await api.generateStructure(payload);
        addMsg("assistant", feedback ? "Here's the updated structure:" : "Here's your video structure:", { structure: data.structure });
        setLastOutput(data.structure);
      } else {
        const payload = { day, ideaKey, durationSeconds: seconds, creatorNotes };
        if (feedback) { payload.feedback = feedback; payload.previous = previous; }
        const data = await api.generateScript(payload);
        addMsg("assistant", feedback ? "Here's the updated script:" : "Here's your script:", { scriptText: data.script });
        setLastOutput(data.script);
      }
      setStage("done");
    } catch (err) {
      fail(err);
      setStage(onErrorStage);
    } finally {
      setBusy(false);
    }
  }

  function chooseDuration(seconds) {
    setDuration(seconds);
    addMsg("user", `${seconds} seconds`);
    generate({ seconds, onErrorStage: "askDuration" });
  }

  function regenerate() {
    addMsg("user", "Regenerate");
    generate({ seconds: duration, onErrorStage: "done" });
  }

  function submitRefine(e) {
    e?.preventDefault();
    const fb = refineInput.trim();
    if (!fb) return;
    addMsg("user", fb);
    setRefineInput("");
    generate({ seconds: duration, feedback: fb, previous: lastOutput, onErrorStage: "done" });
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
    setPendingIdeas(null);
    setOtherLang(null);
    setOutputType("script");
    setDuration(null);
    setLastOutput(null);
    setRefineInput("");
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

        {!busy && stage === "askLanguage" && (
          <div className="choices">
            {LANGUAGES.map((l) => (
              <button key={l.key} className="chip" onClick={() => chooseLanguage(l.key)}>{l.label}</button>
            ))}
          </div>
        )}

        {!busy && stage === "askOtherLanguage" && (
          <div className="choices">
            <button className="chip" onClick={() => chooseOtherLanguage(true)}>Yes, in {langName(otherLang)} too</button>
            <button className="chip chip--ghost" onClick={() => chooseOtherLanguage(false)}>No, continue</button>
          </div>
        )}

        {!busy && stage === "askOutputType" && (
          <div className="ideas">
            {OUTPUT_TYPES.map((o) => (
              <button key={o.key} className="idea-card" onClick={() => chooseOutputType(o.key)}>
                <span className="idea-card__icon">{o.key === "structure" ? "🎬" : "📝"}</span>
                <span className="idea-card__body">
                  <span className="idea-card__label">{o.label}</span>
                  <span className="idea-card__desc">{o.desc}</span>
                </span>
                <span className="idea-card__arrow">›</span>
              </button>
            ))}
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
            <button className="chip" onClick={regenerate}>↻ Regenerate</button>
            <button className="chip chip--ghost" onClick={restart}>+ Make another video</button>
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

        {stage === "done" && (
          <form onSubmit={submitRefine} className="composer__form">
            <textarea
              ref={inputRef}
              rows={2}
              placeholder={`Ask for a change — e.g. "make the hook punchier" or "shorten the opening"…`}
              value={refineInput}
              onChange={(e) => setRefineInput(e.target.value)}
              disabled={busy}
            />
            <div className="composer__actions">
              <button type="submit" className="send-btn" disabled={busy || !refineInput.trim()}>
                <SendIcon />
              </button>
            </div>
          </form>
        )}

        {(stage === "askLanguage" || stage === "askOtherLanguage" || stage === "summarizing" || stage === "askIdea" || stage === "askOutputType" || stage === "askDuration" || stage === "generating") && (
          <p className="composer__hint">
            {stage === "askLanguage" && "Choose a language above"}
            {stage === "askOtherLanguage" && "Choose an option above"}
            {stage === "summarizing" && "Summarizing today's verses…"}
            {stage === "askIdea" && "Choose a video idea above"}
            {stage === "askOutputType" && "Choose script or structure above"}
            {stage === "askDuration" && "Choose a duration above"}
            {stage === "generating" && (outputType === "structure" ? "Building your video structure…" : "Generating your script…")}
          </p>
        )}
      </footer>
    </div>
  );
}

// Normalize a section to a list of options (handles older single-option shape).
function sectionOptions(sec) {
  if (Array.isArray(sec.options) && sec.options.length) return sec.options;
  return [{ visuals: sec.visuals || [], voiceover: sec.voiceover || "" }];
}

function structureToText(s, sel = {}) {
  const lines = [`Core theme: ${s.coreTheme}`, `Concept: "${s.concept}"`, ""];
  (s.sections || []).forEach((sec, i) => {
    const options = sectionOptions(sec);
    const opt = options[Math.min(sel[i] || 0, options.length - 1)];
    lines.push(`[${sec.label} · ${sec.timeRange}]`);
    lines.push("On screen:");
    (opt.visuals || []).forEach((v) => lines.push(`  - ${v}`));
    lines.push(`Voiceover: ${opt.voiceover}`);
    lines.push("");
  });
  return lines.join("\n").trim();
}

function StructureView({ structure }) {
  const [copied, setCopied] = useState(false);
  const [sel, setSel] = useState({});   // section index -> chosen option index

  const copy = () => {
    navigator.clipboard.writeText(structureToText(structure, sel));
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="structure">
      <div className="structure__meta">
        <div className="structure__row">
          <span className="structure__key">Core theme</span>
          <span className="structure__val">{structure.coreTheme}</span>
        </div>
        <div className="structure__row">
          <span className="structure__key">Concept</span>
          <span className="structure__val structure__concept">"{structure.concept}"</span>
        </div>
      </div>

      {(structure.sections || []).some((s) => sectionOptions(s).length > 1) && (
        <p className="structure__hint">Each part has a few options — tap the numbers to compare and mix.</p>
      )}

      {(structure.sections || []).map((sec, i) => {
        const options = sectionOptions(sec);
        const idx = Math.min(sel[i] || 0, options.length - 1);
        const opt = options[idx];

        return (
          <div key={i} className="beat">
            <div className="beat__head">
              <span className="beat__label">{sec.label}</span>
              <span className="beat__time">{sec.timeRange}</span>
            </div>
            {options.length > 1 && (
              <div className="beat__options">
                <span className="beat__options-label">Option</span>
                <div className="beat__opts">
                  {options.map((_, k) => (
                    <button
                      key={k}
                      type="button"
                      className={`beat__opt ${k === idx ? "beat__opt--active" : ""}`}
                      onClick={() => setSel((s) => ({ ...s, [i]: k }))}
                    >
                      {k + 1}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="beat__block">
              <span className="beat__tag">On screen</span>
              <ul className="beat__visuals">
                {(opt.visuals || []).map((v, j) => <li key={j}>{v}</li>)}
              </ul>
            </div>
            <div className="beat__block">
              <span className="beat__tag">Voiceover</span>
              <p className="beat__vo">{opt.voiceover}</p>
            </div>
          </div>
        );
      })}

      <div className="script__actions">
        <button className="chip" onClick={copy}>{copied ? "✓ Copied" : "Copy structure"}</button>
      </div>
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
            <span className="day-badge__label">Chapter</span>
            <span className="day-badge__value">{msg.dayMeta.chapter}</span>
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

      {msg.verseText && (
        <div className="verse-block">
          {msg.verseText.split("\n\n").map((v, i) => (
            <p key={i} className="verse-block__verse">{v}</p>
          ))}
        </div>
      )}

      {msg.summaryPoints && (
        <ul className="summary-points">
          {msg.summaryPoints.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      )}

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

      {msg.structure && <StructureView structure={msg.structure} />}

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
