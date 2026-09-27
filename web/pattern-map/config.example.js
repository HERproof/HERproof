// Copy to config.js and fill in. config.js is optional: without it the app still
// parses, tags with the keyword pass, and generates all three documents, entirely
// in the tab. With it you get the Gemini pass, Cora's Gemini voice and Supabase
// persistence.
//
// config.js is gitignored. Never commit real keys.
window.HERPROOF_CONFIG = {
  // Gemini. Key is exposed to the browser, so for anything past a hackathon demo
  // put this behind the stateless proxy the PRD describes and call that instead.
  gemini: {
    enabled: false,        // Pattern Map's text pass (pattern-map/index.html) runs only when true
    apiKey: "",
    model: "gemini-2.0-flash",
    ttsModel: "gemini-2.5-flash-preview-tts",   // Cora's voice (index.html, app.html)
    voice: "Leda"
  },

  // Supabase. The schema stores tags, flags and counts, never message bodies,
  // so the end-to-end promise in the Vault copy still holds.
  supabase: {
    enabled: false,
    url: "",
    anonKey: ""
  }
};
