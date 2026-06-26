import { createContext, useContext, useEffect, useRef, useState } from "react";
import { api } from "./api";
import "./App.css";

const DURATION_VALUES = [30, 45, 60, 90];

const OUTPUT_TYPE_KEYS = ["script", "structure"];

// Each video idea is a tab. Content-backed ideas map to a source-content section
// (shown in the tab so the creator can pick a specific item to build the video
// around). Creative and Testimony have no source content. The map drives both the
// tab ordering and which mock section feeds each tab.
const IDEA_SECTION = {
  story: "story",
  concept: "concept",
  practice: "challenge",
  extra_info: "extraInfo",
  creative: null,
  testimony: null,
};
const TAB_ORDER = ["story", "concept", "practice", "extra_info", "creative", "testimony"];

const LANGUAGES = [
  { key: "english", label: "English" },
  { key: "hindi", label: "हिन्दी" },
];

const LANG_STORAGE_KEY = "wb_language";

const IDEA_ICONS = {
  concept: "💡",
  practice: "🧘",
  creative: "🎨",
  testimony: "🗣️",
  story: "📖",
  extra_info: "✨",
};

// All user-facing UI text, per language. Generated content (verses, summaries,
// scripts, structures, idea teasers) comes from the backend already in the
// chosen language; this dictionary covers the assistant's own chrome.
const UI = {
  english: {
    greeting:
      "Hi! I'm here to help you script your next Bodhisattva Challenge video. 🙏\n\nWhich day of the plan are you filming? Just tell me the day number (1–365).",
    dayRange: "Please enter a day number between 1 and 365.",
    notReleased: (n, r) =>
      `Day ${n} hasn't been released yet — the plan is live through Day ${r} so far. Pick any day from 1 to ${r}.`,
    variantNote: " (using a draft variant)",
    foundDay: (d, v) => `Here's what I found for Day ${d}${v}. Today's verses:`,
    breakdown: "Here's a simple breakdown of today's verses:",
    pickVerse: "Now, pick a verse and choose the type of video you want to make:",
    howLike: "How would you like it?",
    testimonyPrompt:
      "Perfect. Share a few notes about your own experience with today's teaching — or leave it blank and I'll write a gentle general reflection.",
    howLong: "How long should the video be?",
    yourStructure: "Here's your video structure:",
    updatedStructure: "Here's the updated structure:",
    yourScript: "Here's your script:",
    updatedScript: "Here's the updated script:",
    somethingWrong: (m) => `Something went wrong: ${m}`,
    another: "Let's make another one! Which day are you filming? (1–365)",
    userDay: (n) => `Day ${n}`,
    seconds: (s) => `${s} seconds`,
    secShort: "sec",
    noNotes: "(no notes — keep it general)",
    // composer hints
    hintSummarizing: "Summarizing today's verses…",
    hintPickVerse: "Pick a verse above",
    hintOutputType: "Choose script or structure above",
    hintDuration: "Choose a duration above",
    hintGenScript: "Generating your script…",
    hintGenStructure: "Building your video structure…",
    // controls / placeholders
    dayPlaceholder: "Enter day number (1–365)…",
    testimonyPlaceholder: "Your experience or notes (optional)…",
    refinePlaceholder: `Ask for a change — e.g. "make the hook punchier" or "shorten the opening"…`,
    regenerate: "↻ Regenerate",
    makeAnother: "+ Make another video",
    daysAvailable: "Days available",
    // verse card
    generateAbout: "Generate a video about this:",
    clickExpand: "Click to expand",
    collapse: "Collapse",
    noBackground: "No background content yet for this verse.",
    verseLabel: "Verse",
    sections: { story: "Story", concept: "Concept", challenge: "Challenge", extraInfo: "Extra info" },
    tabLabels: { story: "Story", concept: "Concept", practice: "Challenge", extra_info: "Extra info", creative: "Creative", testimony: "Testimony" },
    generateThis: "Generate this video",
    generateVideo: "Generate video",
    // output types
    outputTypes: {
      script: { label: "Video script", desc: "A ready-to-read spoken script." },
      structure: { label: "Video structure", desc: "A shot-by-shot plan: timed beats, on-screen visuals, and voiceover." },
    },
    // structure view
    coreTheme: "Core theme",
    concept: "Concept",
    optionsHint: "Each part has a few options — tap the numbers to compare and mix.",
    option: "Option",
    onScreen: "On screen",
    voiceover: "Voiceover",
    generateAudio: "Generate audio",
    generating: "Generating…",
    regenerating: "Regenerating…",
    regenAudio: "↻ Regenerate",
    download: "↓ Download",
    copyStructure: "Copy structure",
    copyScript: "Copy script",
    copied: "✓ Copied",
    // day badge
    badgeDay: "Day",
    badgeChapter: "Chapter",
    badgeVerses: "Verses",
    badgeDate: "Date",
  },
  hindi: {
    greeting:
      "नमस्ते! मैं आपकी अगली बोधिसत्व चैलेंज वीडियो की स्क्रिप्ट बनाने में मदद के लिए यहाँ हूँ। 🙏\n\nआप प्लान के किस दिन की शूटिंग कर रहे हैं? बस दिन का नंबर बताइए (1–365)।",
    dayRange: "कृपया 1 से 365 के बीच कोई दिन नंबर डालें।",
    notReleased: (n, r) =>
      `दिन ${n} अभी रिलीज़ नहीं हुआ — प्लान फ़िलहाल दिन ${r} तक ही लाइव है। 1 से ${r} के बीच कोई भी दिन चुनिए।`,
    variantNote: " (ड्राफ़्ट वर्शन इस्तेमाल हो रहा है)",
    foundDay: (d, v) => `दिन ${d}${v} के लिए मुझे यह मिला। आज के श्लोक:`,
    breakdown: "आज के श्लोक का आसान सार यह रहा:",
    pickVerse: "अब एक श्लोक चुनिए और तय कीजिए कि किस तरह का वीडियो बनाना है:",
    howLike: "आप इसे कैसे चाहेंगे?",
    testimonyPrompt:
      "बढ़िया। आज की सीख से जुड़ा अपना कोई अनुभव कुछ शब्दों में बताइए — या खाली छोड़ दीजिए, मैं एक सहज सामान्य विचार लिख दूँगा।",
    howLong: "वीडियो कितना लंबा होना चाहिए?",
    yourStructure: "यह रहा आपका वीडियो स्ट्रक्चर:",
    updatedStructure: "यह रहा अपडेटेड स्ट्रक्चर:",
    yourScript: "यह रही आपकी स्क्रिप्ट:",
    updatedScript: "यह रही अपडेटेड स्क्रिप्ट:",
    somethingWrong: (m) => `कुछ गड़बड़ हो गई: ${m}`,
    another: "चलिए एक और बनाते हैं! आप किस दिन की शूटिंग कर रहे हैं? (1–365)",
    userDay: (n) => `दिन ${n}`,
    seconds: (s) => `${s} सेकंड`,
    secShort: "सेकंड",
    noNotes: "(कोई नोट्स नहीं — सामान्य ही रखें)",
    hintSummarizing: "आज के श्लोक का सार बन रहा है…",
    hintPickVerse: "ऊपर एक श्लोक चुनिए",
    hintOutputType: "ऊपर स्क्रिप्ट या स्ट्रक्चर चुनिए",
    hintDuration: "ऊपर अवधि चुनिए",
    hintGenScript: "आपकी स्क्रिप्ट बन रही है…",
    hintGenStructure: "आपका वीडियो स्ट्रक्चर बन रहा है…",
    dayPlaceholder: "दिन नंबर डालें (1–365)…",
    testimonyPlaceholder: "आपका अनुभव या नोट्स (वैकल्पिक)…",
    refinePlaceholder: `कोई बदलाव बताइए — जैसे "शुरुआत को और दमदार बनाओ" या "ओपनिंग छोटी करो"…`,
    regenerate: "↻ फिर से बनाएँ",
    makeAnother: "+ एक और वीडियो बनाएँ",
    daysAvailable: "उपलब्ध दिन",
    generateAbout: "इस पर एक वीडियो बनाएँ:",
    clickExpand: "खोलने के लिए क्लिक करें",
    collapse: "बंद करें",
    noBackground: "इस श्लोक के लिए अभी कोई अतिरिक्त सामग्री नहीं है।",
    verseLabel: "श्लोक",
    sections: { story: "कहानी", concept: "मुख्य विचार", challenge: "चुनौती", extraInfo: "रोचक जानकारी" },
    tabLabels: { story: "कहानी", concept: "मुख्य विचार", practice: "चुनौती", extra_info: "रोचक जानकारी", creative: "क्रिएटिव", testimony: "आपका अनुभव" },
    generateThis: "इससे वीडियो बनाएँ",
    generateVideo: "वीडियो बनाएँ",
    outputTypes: {
      script: { label: "वीडियो स्क्रिप्ट", desc: "पढ़ने के लिए तैयार, बोली जाने वाली स्क्रिप्ट।" },
      structure: { label: "वीडियो स्ट्रक्चर", desc: "शॉट-दर-शॉट प्लान: समयबद्ध बीट्स, स्क्रीन पर विज़ुअल और वॉयसओवर।" },
    },
    coreTheme: "मुख्य थीम",
    concept: "मुख्य विचार",
    optionsHint: "हर हिस्से के कुछ विकल्प हैं — तुलना और मिलान के लिए नंबरों पर टैप करें।",
    option: "विकल्प",
    onScreen: "स्क्रीन पर",
    voiceover: "वॉयसओवर",
    generateAudio: "ऑडियो बनाएँ",
    generating: "बन रहा है…",
    regenerating: "फिर से बन रहा है…",
    regenAudio: "↻ फिर से बनाएँ",
    download: "↓ डाउनलोड",
    copyStructure: "स्ट्रक्चर कॉपी करें",
    copyScript: "स्क्रिप्ट कॉपी करें",
    copied: "✓ कॉपी हो गया",
    badgeDay: "दिन",
    badgeChapter: "अध्याय",
    badgeVerses: "श्लोक",
    badgeDate: "तारीख़",
  },
};

const LangContext = createContext(UI.english);
const useUI = () => useContext(LangContext);

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

function SpeakerIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: "inline-block", verticalAlign: "middle", marginRight: 5 }}>
      <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
    </svg>
  );
}



export default function App() {
  const [language, setLanguage] = useState(() => {
    const saved = typeof localStorage !== "undefined" && localStorage.getItem(LANG_STORAGE_KEY);
    return saved === "hindi" || saved === "english" ? saved : "english";
  });
  const t = UI[language];

  const [messages, setMessages] = useState([]);
  const [stage, setStage] = useState("askDay");
  const [dayInput, setDayInput] = useState("");
  const [testimonyInput, setTestimonyInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [day, setDay] = useState(null);
  const [ideaKey, setIdeaKey] = useState(null);
  const [ideaFocus, setIdeaFocus] = useState(null); // { text, label } the specific content to build around
  const [creatorNotes, setCreatorNotes] = useState("");
  const [pendingIdeas, setPendingIdeas] = useState(null);
  const [outputType, setOutputType] = useState("script");
  const [duration, setDuration] = useState(null);
  const [lastOutput, setLastOutput] = useState(null);
  const [refineInput, setRefineInput] = useState("");
  const [currentVerseLines, setCurrentVerseLines] = useState([]);
  const [idleZen, setIdleZen] = useState(false);
  const [progress, setProgress] = useState(null);
  const [logoBlessing, setLogoBlessing] = useState(false);
  const logoTaps = useRef(0);
  const logoTimer = useRef(null);
  const blessingShownAt = useRef(0);

  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const greeted = useRef(false);

  const addMsg = (role, content, extra = {}) =>
    setMessages((m) => [...m, { id: nextId(), role, content, ...extra }]);

  useEffect(() => {
    if (greeted.current) return;
    greeted.current = true;
    // Tag the greeting with an i18n key so it re-renders in the current language
    // when the toggle changes (it's the only message shown before any interaction).
    addMsg("assistant", UI[language].greeting, { i18nKey: "greeting" });
    api.health()
      .then((h) => { if (h?.progress) setProgress(h.progress); })
      .catch(() => { /* progress is best-effort */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist the chosen language. Only the greeting (already shown) stays in its
  // original language; everything generated afterward follows the new choice.
  function changeLanguage(next) {
    setLanguage(next);
    try { localStorage.setItem(LANG_STORAGE_KEY, next); } catch { /* ignore */ }
  }

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    if (!busy) setTimeout(() => inputRef.current?.focus(), 50);
  }, [busy, stage]);

  // Idle Zen: after 60s of no interaction, invite a quiet breathing pause.
  // The moment the user moves — mouse, key, scroll, touch — it fades away.
  useEffect(() => {
    let timer;
    const arm = () => {
      clearTimeout(timer);
      setIdleZen(false);
      timer = setTimeout(() => setIdleZen(true), 60_000);
    };
    const events = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "wheel"];
    events.forEach((e) => window.addEventListener(e, arm, { passive: true }));
    arm();
    return () => {
      clearTimeout(timer);
      events.forEach((e) => window.removeEventListener(e, arm));
    };
  }, []);

  const fail = (err) => addMsg("assistant", t.somethingWrong(err.message), { error: true });

  async function submitDay(e) {
    e?.preventDefault();
    const n = parseInt(dayInput, 10);
    if (!n || n < 1 || n > 365) {
      addMsg("assistant", t.dayRange);
      return;
    }
    if (progress?.released && n > progress.released) {
      addMsg("user", t.userDay(n));
      addMsg("assistant", t.notReleased(n, progress.released));
      setDayInput("");
      return;
    }
    addMsg("user", t.userDay(n));
    setDayInput("");
    setBusy(true);
    setStage("summarizing");
    try {
      const data = await api.getDay(n, language);
      setDay(data.day);
      setPendingIdeas(data.availableIdeas);
      setCurrentVerseLines(data.verseLines || []);
      const variantNote = data.isVariant ? t.variantNote : "";
      addMsg("assistant",
        t.foundDay(data.day, variantNote),
        {
          dayMeta: { day: n, chapter: chapterFrom(data.versesLabel), verses: versesOnly(data.versesLabel), date: data.date },
          verseLines: data.verseLines,
        }
      );
      // The language is global, so go straight to the breakdown in that language,
      // then the idea cards — no mid-flow language question.
      const summary = await api.verseSummary({ day: data.day, language });
      addMsg("assistant", t.breakdown, { summaryPoints: summary.points });
      showIdeas();
    } catch (err) {
      fail(err);
      setStage("askDay");
    } finally {
      setBusy(false);
    }
  }

  function showIdeas() {
    addMsg("assistant", t.pickVerse);
    setStage("askVerseIdea");
  }

  function chooseIdea(idea, focus = null) {
    setIdeaKey(idea.key);
    setIdeaFocus(focus);
    addMsg("user", focus?.label || idea.label);
    addMsg("assistant", t.howLike);
    setStage("askOutputType");
  }

  function chooseOutputType(type) {
    setOutputType(type);
    addMsg("user", t.outputTypes[type]?.label || type);
    if (ideaKey === "testimony") {
      addMsg("assistant", t.testimonyPrompt);
      setStage("askTestimony");
    } else {
      askDuration();
    }
  }

  function submitTestimony(e) {
    e?.preventDefault();
    setCreatorNotes(testimonyInput);
    addMsg("user", testimonyInput.trim() || t.noNotes);
    setTestimonyInput("");
    askDuration();
  }

  function askDuration() {
    addMsg("assistant", t.howLong);
    setStage("askDuration");
  }

  async function generate({ seconds, feedback = "", previous = null, onErrorStage }) {
    setBusy(true);
    setStage("generating");
    try {
      const focusFields = ideaFocus
        ? { focus: ideaFocus.text, focusLabel: ideaFocus.typeLabel || ideaFocus.label }
        : {};
      if (outputType === "structure") {
        const payload = { day, ideaKey, durationSeconds: seconds, creatorNotes, language, ...focusFields };
        if (feedback) { payload.feedback = feedback; payload.previous = previous; }
        const data = await api.generateStructure(payload);
        addMsg("assistant", feedback ? t.updatedStructure : t.yourStructure, { structure: data.structure });
        setLastOutput(data.structure);
      } else {
        const payload = { day, ideaKey, durationSeconds: seconds, creatorNotes, language, ...focusFields };
        if (feedback) { payload.feedback = feedback; payload.previous = previous; }
        const data = await api.generateScript(payload);
        addMsg("assistant", feedback ? t.updatedScript : t.yourScript, { scriptText: data.script });
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
    addMsg("user", t.seconds(seconds));
    generate({ seconds, onErrorStage: "askDuration" });
  }

  function regenerate() {
    addMsg("user", t.regenerate);
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

  function tapLogo() {
    setIdleZen(false);
    logoTaps.current += 1;
    clearTimeout(logoTimer.current);
    if (logoTaps.current >= 5) {
      logoTaps.current = 0;
      blessingShownAt.current = Date.now();
      setLogoBlessing(true);
      setTimeout(() => setLogoBlessing(false), 3000);
    } else {
      logoTimer.current = setTimeout(() => { logoTaps.current = 0; }, 1200);
    }
  }

  function restart() {
    setStage("askDay");
    setDay(null);
    setIdeaKey(null);
    setIdeaFocus(null);
    setCreatorNotes("");
    setPendingIdeas(null);
    setOutputType("script");
    setDuration(null);
    setLastOutput(null);
    setRefineInput("");
    setCurrentVerseLines([]);
    addMsg("assistant", t.another);
  }

  return (
   <LangContext.Provider value={t}>
    <div className="app">
      <header className="app__header">
        <img src="/logo.png" width="32" height="32" alt="WeBuddhist" onClick={tapLogo} className={`logo-tap${logoBlessing ? " logo-tap--spin" : ""}`} />
        <div className="header__text">
          <h1>WeBuddhist Creator Assistant</h1>
          <p>Bodhisattva Challenge · Video script generator</p>
        </div>
        <div className="lang-toggle" role="group" aria-label="Language">
          {LANGUAGES.map((l) => (
            <button
              key={l.key}
              type="button"
              className={`lang-toggle__btn${language === l.key ? " lang-toggle__btn--active" : ""}`}
              onClick={() => changeLanguage(l.key)}
              disabled={busy}
            >
              {l.label}
            </button>
          ))}
        </div>
        {progress?.released > 0 && (
          <div
            className="progress-pill"
            title={`The plan started ${progress.startDate}. A new day unlocks every day.`}
          >
            <div className="progress-pill__top">
              <span className="progress-pill__label">{t.daysAvailable}</span>
              <span className="progress-pill__count">{progress.released} / {progress.total}</span>
            </div>
            <div className="progress-pill__bar">
              <div
                className="progress-pill__fill"
                style={{ width: `${Math.max(2, (progress.released / progress.total) * 100)}%` }}
              />
            </div>
          </div>
        )}
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

        {!busy && stage === "askVerseIdea" && (
          <div className="vcards">
            {currentVerseLines.map((verse, idx) => (
              <VerseCard
                key={idx}
                verse={verse}
                idx={idx}
                ideas={pendingIdeas || []}
                onChooseIdea={chooseIdea}
                busy={busy}
              />
            ))}
          </div>
        )}

        {!busy && stage === "askOutputType" && (
          <div className="ideas">
            {OUTPUT_TYPE_KEYS.map((key) => (
              <button key={key} className="idea-card" onClick={() => chooseOutputType(key)}>
                <span className="idea-card__icon">{key === "structure" ? "🎬" : "📝"}</span>
                <span className="idea-card__body">
                  <span className="idea-card__label">{t.outputTypes[key].label}</span>
                  <span className="idea-card__desc">{t.outputTypes[key].desc}</span>
                </span>
                <span className="idea-card__arrow">›</span>
              </button>
            ))}
          </div>
        )}

        {!busy && stage === "askDuration" && (
          <div className="choices">
            {DURATION_VALUES.map((value) => (
              <button key={value} className="chip" onClick={() => chooseDuration(value)}>{value} {t.secShort}</button>
            ))}
          </div>
        )}

        {!busy && stage === "done" && (
          <div className="choices">
            <button className="chip" onClick={regenerate}>{t.regenerate}</button>
            <button className="chip chip--ghost" onClick={restart}>{t.makeAnother}</button>
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
              placeholder={t.dayPlaceholder}
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
              placeholder={t.testimonyPlaceholder}
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
              placeholder={t.refinePlaceholder}
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

        {(stage === "summarizing" || stage === "askVerseIdea" || stage === "askOutputType" || stage === "askDuration" || stage === "generating") && (
          <p className="composer__hint">
            {stage === "summarizing" && t.hintSummarizing}
            {stage === "askVerseIdea" && t.hintPickVerse}
            {stage === "askOutputType" && t.hintOutputType}
            {stage === "askDuration" && t.hintDuration}
            {stage === "generating" && (outputType === "structure" ? t.hintGenStructure : t.hintGenScript)}
          </p>
        )}
      </footer>

      {logoBlessing && (
        <div className="blessing" onClick={() => { if (Date.now() - blessingShownAt.current > 1000) setLogoBlessing(false); }}>
          <p className="blessing__text">May all beings be happy</p>
        </div>
      )}

      {idleZen && (
        <div className="zen" onClick={() => setIdleZen(false)} role="presentation">
          <div className="zen__breath" />
          <p className="zen__cue">breathe</p>
          <p className="zen__hint">take a breath — move to return</p>
        </div>
      )}
    </div>
   </LangContext.Provider>
  );
}

function getMockVerseContent(idx) {
  // Each section is an array: [] = no content, [x] = one item, [x, y] = multiple.
  const pool = [
    {
      story: [
        "A young student once asked his teacher why meditating on kindness felt so difficult. The teacher said nothing — he simply handed the student a mirror. The student stared at it, confused. Days later, he understood: kindness begins by seeing yourself clearly.",
        "A grandmother who survived great hardship was once asked how she stayed so kind. She said: 'I decided long ago that bitterness was too heavy to carry. I put it down.'",
      ],
      concept: [
        "Bodhicitta — the wish to become enlightened for all beings — is not just a noble intention. It is the root from which every positive quality grows. Even a small seed of it transforms ordinary actions into something vast.",
      ],
      challenge: [
        "Today, before responding to anyone, pause for one breath and silently wish them well. Just one breath. Notice what changes.",
      ],
      extraInfo: [
        "The Bodhicharyavatara was composed by Shantideva in 8th-century India at Nalanda University — one of the ancient world's greatest centers of learning, home to over 10,000 scholars.",
      ],
    },
    {
      story: [
        "A monk who had studied patience for years was once insulted by a rude traveler. His students expected him to remain calm. Instead, he laughed. Later they asked why. He said: 'After all those years, anger still arrived. But this time, it didn't stay.'",
      ],
      concept: [
        "Mindfulness is not about having a perfectly calm mind. It is about noticing when the mind has wandered — and returning, again and again, without judgment. The return itself is the practice.",
      ],
      challenge: [
        "Choose one moment today when you feel frustrated and do nothing for five seconds. Just observe the feeling without acting on it. See what happens on its own.",
      ],
      extraInfo: [],
    },
    {
      story: [],
      concept: [
        "Confession in Buddhist practice is not about guilt — it is about clarity. Acknowledging harm we've caused creates the space to do differently. The past is fixed; how we move forward is not.",
      ],
      challenge: [
        "Think of one action you regret from this week. Without harsh self-judgment, simply acknowledge it: 'I acted from fear' or 'I acted from anger.' Then let it go. Done.",
      ],
      extraInfo: [
        "Shantideva is believed to have recited the entire Bodhicharyavatara spontaneously during an assembly at Nalanda, apparently floating in the air. Whether literal or legendary, the story captures how transformative the text felt to those who first heard it.",
      ],
    },
  ];
  return pool[idx % pool.length];
}

function VerseCard({ verse, idx, ideas, onChooseIdea, busy }) {
  const t = useUI();
  const [open, setOpen] = useState(false);
  const content = getMockVerseContent(idx);

  // Each tab is a video idea. Content-backed ideas (Story/Concept/Challenge/
  // Extra info) appear when this verse has source material for them; Creative
  // and Testimony are always offered (they have no source content).
  const ideaByKey = Object.fromEntries((ideas || []).map((i) => [i.key, i]));
  const itemsFor = (key) => {
    const section = IDEA_SECTION[key];
    return section ? content[section] || [] : [];
  };
  const ideaObj = (key) => ideaByKey[key] || { key, label: t.tabLabels[key], teaser: "" };

  const tabs = TAB_ORDER.filter((key) =>
    IDEA_SECTION[key] ? itemsFor(key).length > 0 : !!ideaByKey[key]
  );
  const [activeTab, setActiveTab] = useState(tabs[0] ?? "concept");

  function handleToggle() {
    if (!open && tabs.length > 0 && !tabs.includes(activeTab)) {
      setActiveTab(tabs[0]);
    }
    setOpen(!open);
  }

  const activeIdea = ideaObj(activeTab);
  const activeItems = itemsFor(activeTab);

  return (
    <div className={`vcard${open ? " vcard--open" : ""}`}>
      <button className="vcard__header" onClick={handleToggle} aria-expanded={open}>
        <span className="vcard__num">
          <span className="vcard__num-label">{t.verseLabel}</span>
          <span className="vcard__num-value">{verse.n || idx + 1}</span>
        </span>
        <p className="vcard__text">{verse.text}</p>
        <svg className={`vcard__arrow${open ? " vcard__arrow--open" : ""}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="vcard__body">
          <div className="vcard__tabs">
            {tabs.map((key) => {
              const count = itemsFor(key).length;
              return (
                <button
                  key={key}
                  className={`vcard__tab${activeTab === key ? " vcard__tab--active" : ""}`}
                  onClick={() => setActiveTab(key)}
                >
                  <span className="vcard__tab-icon">{IDEA_ICONS[key] || "▸"}</span>
                  {t.tabLabels[key] || key}
                  {count > 1 && <span className="vcard__tab-count">{count}</span>}
                </button>
              );
            })}
          </div>

          {activeItems.length > 0 ? (
            // Content-backed tab: each source item builds its own focused video.
            <div className="vcard__items">
              {activeItems.map((item, i) => (
                <div key={i} className="vcard__item">
                  {activeItems.length > 1 && (
                    <span className="vcard__item-num">{t.tabLabels[activeTab]} {i + 1}</span>
                  )}
                  <p>{item}</p>
                  <button
                    className="vcard__gen"
                    disabled={busy}
                    onClick={() =>
                      onChooseIdea(activeIdea, {
                        text: item,
                        typeLabel: t.tabLabels[activeTab],
                        label: activeItems.length > 1
                          ? `${t.tabLabels[activeTab]} ${i + 1}`
                          : activeIdea.label,
                      })
                    }
                  >
                    {t.generateThis} <span className="vcard__gen-arrow">›</span>
                  </button>
                </div>
              ))}
            </div>
          ) : (
            // Creative / Testimony (or a tab with no source content yet): one
            // panel describing the idea, with a single generate action.
            <div className="vcard__items">
              <div className="vcard__item">
                <p>{activeIdea?.teaser}</p>
                <button
                  className="vcard__gen"
                  disabled={busy}
                  onClick={() => onChooseIdea(activeIdea, null)}
                >
                  {t.generateVideo} <span className="vcard__gen-arrow">›</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Force a real file download. The <a download> attribute is ignored for
// cross-origin URLs (the audio is served from the backend origin), so we fetch
// the file as a blob and download that instead — which keeps it on-page.
async function downloadAudio(url, filename) {
  const name = filename || url.split("/").pop() || "audio.wav";
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(objectUrl);
  } catch {
    // Last resort if the fetch fails: open the file directly.
    window.open(url, "_blank", "noopener");
  }
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
  const t = useUI();
  const [copied, setCopied] = useState(false);
  const [sel, setSel] = useState({});   // section index -> chosen option index
  const [vo, setVo] = useState({});      // "beat:option" -> { url, loading, error }

  const copy = () => {
    navigator.clipboard.writeText(structureToText(structure, sel));
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  const makeVO = async (key, text) => {
    const line = (text || "").trim();
    if (!line) return;
    setVo((v) => ({ ...v, [key]: { ...v[key], loading: true, error: null } }));
    try {
      const data = await api.generateAudio({ script: line });
      setVo((v) => ({ ...v, [key]: { url: data.audioUrl, loading: false, error: null } }));
    } catch (err) {
      setVo((v) => ({ ...v, [key]: { ...v[key], loading: false, error: err.message } }));
    }
  };

  return (
    <div className="structure">
      <div className="structure__meta">
        <div className="structure__row">
          <span className="structure__key">{t.coreTheme}</span>
          <span className="structure__val">{structure.coreTheme}</span>
        </div>
        <div className="structure__row">
          <span className="structure__key">{t.concept}</span>
          <span className="structure__val structure__concept">"{structure.concept}"</span>
        </div>
      </div>

      {(structure.sections || []).some((s) => sectionOptions(s).length > 1) && (
        <p className="structure__hint">{t.optionsHint}</p>
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
                <span className="beat__options-label">{t.option}</span>
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
              <span className="beat__tag">{t.onScreen}</span>
              <ul className="beat__visuals">
                {(opt.visuals || []).map((v, j) => <li key={j}>{v}</li>)}
              </ul>
            </div>
            <div className="beat__block">
              <span className="beat__tag">{t.voiceover}</span>
              <p className="beat__vo">{opt.voiceover}</p>
              {(() => {
                const key = `${i}:${idx}`;
                const state = vo[key] || {};
                const hasText = !!(opt.voiceover || "").trim();
                return (
                  <div className="beat__audio">
                    {!state.url && (
                      <button
                        type="button"
                        className="chip"
                        disabled={!hasText || state.loading}
                        onClick={() => makeVO(key, opt.voiceover)}
                      >
                        {state.loading ? t.generating : <><SpeakerIcon />{t.generateAudio}</>}
                      </button>
                    )}
                    {state.url && (
                      <div className="script__audio">
                        <audio controls src={state.url} />
                        <button
                          type="button"
                          className="chip"
                          onClick={() => downloadAudio(state.url, `voiceover-${sec.label || "beat"}-${idx + 1}.wav`)}
                        >
                          {t.download}
                        </button>
                        <button
                          type="button"
                          className="chip"
                          disabled={state.loading}
                          onClick={() => makeVO(key, opt.voiceover)}
                        >
                          {state.loading ? t.regenerating : t.regenAudio}
                        </button>
                      </div>
                    )}
                    {state.error && <p className="beat__audio-err">{state.error}</p>}
                  </div>
                );
              })()}
            </div>
          </div>
        );
      })}

      <div className="script__actions">
        <button className="chip" onClick={copy}>{copied ? t.copied : t.copyStructure}</button>
      </div>
    </div>
  );
}

function Bubble({ msg, onChooseIdea, onMakeAudio, busy }) {
  const t = useUI();
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
            <span className="day-badge__label">{t.badgeDay}</span>
            <span className="day-badge__value">{msg.dayMeta.day}</span>
          </div>
          <div className="day-badge__divider" />
          <div className="day-badge__item">
            <span className="day-badge__label">{t.badgeChapter}</span>
            <span className="day-badge__value">{msg.dayMeta.chapter}</span>
          </div>
          <div className="day-badge__divider" />
          <div className="day-badge__item">
            <span className="day-badge__label">{t.badgeVerses}</span>
            <span className="day-badge__value">{msg.dayMeta.verses}</span>
          </div>
          <div className="day-badge__divider" />
          <div className="day-badge__item">
            <span className="day-badge__label">{t.badgeDate}</span>
            <span className="day-badge__value">{msg.dayMeta.date}</span>
          </div>
        </div>
      )}

      <div className="bubble__text">{msg.i18nKey && t[msg.i18nKey] ? t[msg.i18nKey] : msg.content}</div>

      {(() => {
        const lines = msg.verseLines
          || (msg.verseText ? msg.verseText.split("\n\n").map((txt) => ({ n: "", text: txt })) : null);
        if (!lines || !lines.length) return null;
        return (
          <div className="verse-block">
            {lines.map((v, i) => (
              <div key={i} className="verse-line">
                <span className="verse-line__dot" />
                <p className="verse-line__text">{v.text}</p>
              </div>
            ))}
          </div>
        );
      })()}

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
            <button className="chip" onClick={copy}>{copied ? t.copied : t.copyScript}</button>
            {!msg.audioUrl && (
              <button className="chip" onClick={() => onMakeAudio(msg.scriptText, msg.id)} disabled={busy}>
                <SpeakerIcon />{t.generateAudio}
              </button>
            )}
          </div>
          {msg.audioUrl && (
            <div className="script__audio">
              <audio controls src={msg.audioUrl} />
              <button
                type="button"
                className="chip"
                onClick={() => downloadAudio(msg.audioUrl, "script-audio.wav")}
              >
                {t.download}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
