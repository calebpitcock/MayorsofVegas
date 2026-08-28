/* ============================================================================
   Beer League Flappy Buck — Firebase credentials
   ----------------------------------------------------------------------------
   These are Caleb's real project credentials. The apiKey is NOT a secret --
   Google publishes it in every web app on purpose. What actually protects the
   database is the Rules tab in the Firebase console. See SETUP.md step 5.
   ============================================================================ */
window.FIREBASE_CONFIG = {
  apiKey:            "AIzaSyBBvgKv3_9ZVq-kb4JAtlAEluFqWBiqyGA",
  authDomain:        "mayors-of-vegas-beer-league.firebaseapp.com",
  databaseURL:       "https://mayors-of-vegas-beer-league-default-rtdb.firebaseio.com",
  projectId:         "mayors-of-vegas-beer-league",
  storageBucket:     "mayors-of-vegas-beer-league.firebasestorage.app",
  messagingSenderId: "1097247174678",

  /* NOTE: this appId came from an iOS app registration (see the ":ios:" in it).
     The leaderboard will still work, because Realtime Database access is
     governed by databaseURL + Rules, not by appId. But the correct value comes
     from registering a WEB app -- SETUP.md step 2 -- and will read ":web:".  */
  appId: "1:1097247174678:web:28c1dbbd2ce2a267abc537"};
