(() => {
  "use strict";

  const { esc, icon, appIcon, debounce, toast } = window.PAKAL;
  const API = { apps: "/api/apps", status: "/api/status", ui: "/api/ui", actions: "/api/actions/config" };
  const VIEWS = ["home", "apps", "bundles", "platforms", "docker", "actions"];
  const VIEW_TOGGLES = { bundles: "tab_bundles", platforms: "tab_platforms", docker: "tab_docker", actions: "tab_actions" };
  const UPLOAD_CONCURRENCY = 3;
  const SCAN_POLL_MS = 1500;
  const LIVE_SYNC_MS = 30000;
  const EXPECT_CHANGE_MS = 25000;
  const UI_REFRESH_TICKS = 4;
  const ANNOUNCEMENT_KEY = "pakal.announcement.read";

  // ------------------------------------------------------------------- i18n

  const I18N = {
    he: {
      docTitle: "פ.ק.ל | פורטל התוכנות והפיתוח",
      brand: "פ.ק.ל",
      brandSub: "פורטל התוכנות והפיתוח",
      heroBrand: "פ.ק.ל",
      heroTitle: "פורטל התוכנות והפיתוח",
      footerCredits: "נבנה ומתוחזק ב-❤️ על ידי צוות שרתים",
      themeToggle: "מצב תצוגה בהיר/כהה",
      syncLabel: "סנכרן / רענן",
      syncDone: (n) => `הקטלוג סונכרן מהשרת · ${n} תוכנות`,
      navHome: "סקירה",
      navApps: "מאגר התוכנות",
      navStacks: "ערכות לפי תפקיד",
      navPlatforms: "פלטפורמות",
      admin: "ניהול",
      search: "חיפוש",
      clearSearch: "נקה חיפוש",
      searchPlaceholder: "חיפוש תוכנה…",
      heroSearchPlaceholder: "חיפוש לפי שם, גרסה או תגית - לדוגמה python 3.13",
      close: "סגירה",
      osFilter: "מערכת הפעלה",
      sortBy: "מיון",
      osAll: "כל מערכות ההפעלה",
      osUniversal: "כללי",
      sortName: "מיון לפי שם",
      sortUpdated: "עודכן לאחרונה",
      sortSize: "מיון לפי גודל",
      coreTools: "כלים מרכזיים",
      recent: "עודכנו לאחרונה",
      viewAll: "הצג הכל",
      download: "הורדה",
      downloadLatest: "הורדת הגרסה האחרונה",
      downloadFor: (os) => `הורדה ל-${os}`,
      downloadAll: "הורד הכל (ZIP)",
      details: "פרטים",
      tools: (n) => (n === 1 ? "כלי אחד" : `${n} כלים`),
      installers: (n) => (n === 1 ? "מתקין אחד" : `${n} מתקינים`),
      results: (shown, total) => `${shown} מתוך ${total} תוכנות`,
      clearFilters: "ניקוי סינון",
      noResultsTitle: "לא נמצאו תוכנות",
      noResultsText: "נסו מונח חיפוש אחר או נקו את הסינון.",
      emptyTitle: "המאגר ריק",
      emptyText: "הוסיפו תיקייה לכל תוכנה עם קבצי התקנה (exe, msi, iso, zip) - המאגר ייסרק אוטומטית.",
      rootMissingTitle: "תיקיית המאגר אינה זמינה",
      rootMissingText: "לא ניתן לגשת לשיתוף הקבצים. ודאו שהוא מחובר לקונטיינר.",
      loadErrorTitle: "שגיאה בטעינת הקטלוג",
      retry: "נסה שוב",
      officialInstallers: "מתקינים רשמיים",
      colFile: "קובץ",
      colVersion: "גרסה",
      colOs: "מערכת",
      colDate: "תאריך",
      colSize: "גודל",
      latest: "אחרונה",
      noVersion: "ללא גרסה",
      bundleCtx: (size, n) => `חבילה מלאה · ${size} · ${n.toLocaleString()} קבצים`,
      latestVersion: "גרסה אחרונה",
      platformsLbl: "מערכות הפעלה",
      updated: "עודכן",
      totalSize: "גודל כולל",
      homepage: "אתר הבית",
      missingTools: (n) => `${n} לא זמינים במאגר`,
      moreTools: (n) => `ועוד ${n}`,
      noStackTools: "אף אחד מכלי הערכה לא נמצא במאגר",
      noStacks: "טרם הוגדרו ערכות. ניתן להגדיר אותן בממשק הניהול.",
      noPlatforms: "טרם הוגדרו פלטפורמות. ניתן להגדיר אותן בממשק הניהול.",
      stackDownloadStart: (n, name) => `מכין קובץ ZIP אחד עם ${n} מתקינים מ-"${name}"`,
      downloadStarted: (name) => `ההורדה החלה: ${name}`,
      scanning: "סורק את המאגר…",
      syncedAt: (time) => `סונכרן ${time}`,
      noFilesForOs: "אין מתקינים למערכת הפעלה זו",
      all: "הכל",
      stackTools: "כלים בערכה",
      stackOs: "מערכת יעד",
      feedbackNav: "הצעת ייעול / דיווח",
      feedbackTitle: "ייעול ופניות",
      feedbackIntro: "יש לכם רעיון לשיפור, נתקלתם בתקלה או חסר לכם כלי? ספרו לנו.",
      fbCategory: "סוג הפנייה",
      fbCat_suggestion: "הצעת ייעול",
      fbCat_bug: "דיווח על תקלה",
      fbCat_app_request: "בקשת כלי/אפליקציה חדשה",
      fbSubject: "נושא",
      fbSubjectPh: "תיאור קצר של הפנייה",
      fbMessage: "תיאור מפורט",
      fbMessagePh: "פרטו ככל הניתן - מה קרה, מה ציפיתם שיקרה, או מה הייתם רוצים לקבל",
      fbSender: "פרטי הפונה (ממולאים אוטומטית)",
      fbFullName: "שם מלא",
      fbAccount: "מזהה משתמש",
      fbIp: "כתובת IP",
      fbTime: "חותמת זמן",
      fbGuest: "אורח (לא מחובר)",
      fbSubmit: "שליחת הפנייה",
      fbSending: "שולח…",
      fbSuccess: "פנייתך התקבלה בהצלחה",
      fbRequired: "יש למלא נושא ותיאור",
      fbThrottled: "נשלחו פניות רבות מדי. נסו שוב בעוד מספר דקות.",
      signIn: "התחברות",
      signOut: "התנתקות",
      reloginCountdown: (s) => `התנתקת מהמערכת. התחברות מחדש אוטומטית בעוד ${s} שניות…`,
      reloginNow: "התחבר עכשיו",
      cancel: "ביטול",
      reloginNoSession: "לא נמצא חיבור פעיל ב-Keycloak. ניתן להתחבר מחדש בכל עת.",
      dismiss: "סגירה",
      ssoFailed: "ההתחברות דרך Keycloak נכשלה",
      signInTitle: "התחברות לפורטל", signInIntro: "התחברו כדי שהפניות ישויכו לחשבון שלכם.",
      signInLdapHint: "שם המשתמש והסיסמה של הרשת הארגונית", signInSso: "כניסה עם SSO", signInOr: "או",
      adUsername: "שם משתמש", adUsernamePh: "הזינו שם משתמש", adPassword: "סיסמה", adPasswordPh: "הזינו סיסמה",
      adSignIn: "כניסה", adSigningIn: "מתחבר…", adFailed: "שם המשתמש או הסיסמה שגויים",
      adUnavailable: "שירות הספרייה (AD) אינו זמין כרגע", adThrottled: (s) => `יותר מדי ניסיונות. נסו שוב בעוד ${s} שניות.`,
      signedInAs: (n) => `שלום, ${n}`, signedOut: "התנתקת מהפורטל",
      signingOut: "מתנתק…",
      navActions: "פעולות",
      navDocker: "מאגר Docker",
      actionsSubtitle: "כלים בשירות עצמי מול תשתיות הפיתוח המקומיות. בחרו כלי כדי להתחיל.",
      hubBack: "חזרה למרכז הפעולות",
      hubNexusTitle: "העלאת ארטיפקטים ל-Nexus",
      hubNexusDesc: "העלאה מרוכזת של חבילות Python, NPM ומודולי PowerShell למאגרי ה-Nexus המקומיים - גם תיקיות עם מאות קבצים.",
      hubStatusLoading: "טוען הגדרות…", hubStatusError: "לא ניתן לטעון את ההגדרות",
      hubNexusNotConfigured: "Nexus טרם הוגדר",
      hubUploading: (done, total) => `מעלה · ${done} מתוך ${total}`,
      hubQueued: (n) => (n === 1 ? "קובץ אחד בתור" : `${n} קבצים בתור`),
      hubSignIn: "נדרשת התחברות להעלאה", hubReady: "מוכן",
      upIntro: "גררו חבילות Python, NPM ומודולי PowerShell - מאגר היעד נבחר אוטומטית לפי סיומת הקובץ וניתן לשנות אותו בכל שורה.",
      upDrop: "גררו לכאן קבצים או תיקיות",
      upBrowse: "או לחצו לבחירת קבצים",
      upLimit: (mb) => `עד ${mb}MB לקובץ`,
      upKind_pypi: "Python (PyPI)", upKind_npm: "NPM", upKind_powershell: "PowerShell",
      upNoRepo: "לא הוגדר מאגר",
      upNotConfigured: "החיבור ל-Nexus טרם הוגדר. מנהלי המערכת יכולים להגדיר אותו בממשק הניהול.",
      upSignIn: "יש להתחבר כדי להעלות חבילות. ניתן כבר עכשיו להכין את רשימת הקבצים.",
      upConfigError: "לא ניתן לטעון את הגדרות ההעלאה",
      upQueue: "תור העלאה",
      upColFile: "קובץ", upColSize: "גודל", upColTarget: "מאגר יעד", upColStatus: "סטטוס",
      upStatus_pending: "ממתין", upStatus_uploading: "מעלה", upStatus_success: "הצליח", upStatus_failed: "נכשל", upStatus_exists: "קיים כבר", upStatus_cancelled: "בוטל",
      upFormats: "פורמטים נתמכים", upFormatsHint: "אילו קבצים מזוהים ולאן הם נשלחים",
      upFolder: "בחירת תיקייה", upFolderHint: "סריקה של כל תת-התיקיות",
      upFormatsTitle: "פורמטים נתמכים וזיהוי אוטומטי",
      upFormatsIntro: "סוג החבילה ומאגר היעד נקבעים לפי סיומת הקובץ. זה מה שמזוהה אוטומטית ולאן כל פורמט נשלח:",
      upFmtColExt: "סיומת", upFmtColType: "סוג חבילה", upFmtColDesc: "תיאור", upFmtColRepo: "מאגרי יעד",
      upFmt_whl: "Python wheel - חבילה בנויה", upFmt_targz: "Python source distribution (sdist)",
      upFmt_tgz: "חבילת NPM (פלט של npm pack)", upFmt_nupkg: "מודול PowerShell / חבילת NuGet",
      upFmtAlt: (kinds) => `ניתן להעביר גם ל: ${kinds}`,
      upFmtNoteAuto: "כל קובץ מקבל מאגר יעד אוטומטי לפי הסיומת - הראשון ברשימת המאגרים של אותו סוג.",
      upFmtNoteOverride: "ניתן לשנות את מאגר היעד בכל שורה, או לסמן כמה שורות ולהחליף לכולן יחד.",
      upFmtNoteFolder: "בגרירת תיקייה נסרקות כל תת-התיקיות, וקבצים שאינם חבילות נתמכות מדולגים.",
      upFmtNoteDupes: "קבצים כפולים (אותו שם ואותו גודל) מתווספים לתור פעם אחת בלבד.",
      upSelectAll: "סימון כל הקבצים המוצגים בסינון", upSelectRow: (name) => `סימון ${name}`,
      upSelected: (n) => (n === 1 ? "קובץ אחד מסומן" : `${n} קבצים מסומנים`), upNoneSelected: "סמנו קבצים כדי לשנות להם יעד",
      upBulkPlaceholder: "בחירת מאגר יעד…", upBulkApply: "שינוי יעד לכל המסומנים",
      upBulkApplied: (n, target) => `היעד עודכן ל-${target} (${n} קבצים שונו)`,
      upBulkSkipped: (n) => `${n} קבצים מסומנים דולגו - הפורמט שלהם לא מתאים למאגר או שהם כבר הועלו`,
      upRemoveSelected: "הסרת המסומנים",
      upAbort: "ביטול / עצירת ההעלאה", upAborting: "עוצר…",
      upAborted: (done, cancelled, pending) => `ההעלאה נעצרה: ${done} הושלמו · ${cancelled} בוטלו · ${pending} ממתינים`,
      upCancelledLate: "בוטל אחרי שהקובץ הועבר - ייתכן שהפרסום ב-Nexus כבר הושלם",
      upIncompatible: "לא תואם",
      upOverrideOff: "שינוי מאגר היעד חסום על ידי מנהל המערכת",
      upTargetLocked: "לא ניתן לשנות יעד לקובץ שכבר נשלח",
      upManual: "ידני", upManualHint: (auto) => `נבחר ידנית · היעד האוטומטי: ${auto}`,
      upFilterAll: "הכל", upNoMatch: "אין קבצים בסטטוס הזה",
      upShowing: (shown, total) => `מוצגים ${shown} מתוך ${total}`,
      upShowMore: (n) => `הצגת עוד (${n} נותרו)`, upShowLess: "הצגת פחות",
      upPublishing: "מפרסם ב-Nexus…",
      upPublishedTo: (repo) => `פורסם במאגר ${repo}`, upExistsIn: (repo) => `הגרסה כבר קיימת במאגר ${repo}`,
      upStart: (n) => (n === 1 ? "העלאת קובץ אחד" : `העלאת ${n} קבצים`),
      upRetry: "ניסיון חוזר לכושלים ולמבוטלים",
      upClearDone: "ניקוי שהושלמו",
      upClearAll: "ניקוי הכל",
      upBatch: (done, total) => `${done} מתוך ${total} קבצים`,
      upDone: (s, e, f) => `ההעלאה הסתיימה: ${s} הצליחו · ${e} קיימים כבר · ${f} נכשלו`,
      upUnsupported: "סוג קובץ לא נתמך (‎.whl ‎.tar.gz ‎.tgz ‎.nupkg)",
      upNoTarget: "לא הוגדר מאגר יעד לסוג חבילה זה",
      upTooLarge: (mb) => `הקובץ גדול מ-${mb}MB`,
      upAdded: (n) => (n === 1 ? "קובץ אחד נוסף לתור" : `${n} קבצים נוספו לתור`),
      upDuplicates: (n) => `${n} קבצים כפולים דולגו`,
      upSkipped: (n) => `${n} קבצים שאינם חבילות נתמכות דולגו`,
      upRemove: "הסרה מהתור", upCancel: "ביטול העלאה", upCancelled: "ההעלאה בוטלה",
      upNetwork: "שגיאת רשת - החיבור לשרת נכשל",
      upLeave: "העלאות עדיין מתבצעות. לעזוב את הדף?",
      cuAdd: "הוספת גרסה / העלאת קובץ", cuAdminOnly: "מנהלים בלבד",
      cuIntro: (folder) => `הקובץ יישמר ישירות בתיקיית התוכנה בשרת (\u2068${folder}\u2069) והקטלוג יסונכרן מיד לכל המשתמשים.`,
      cuFolder: "תיקיית גרסה (רשות)", cuFolderHint: "השאירו ריק כדי לשמור בתיקייה הראשית של התוכנה.",
      cuOverwrite: "החלפת הקובץ הקיים בשם זה", cuUpload: "העלאה לשרת", cuChoose: "בחירת קובץ אחר",
      cuUploading: (pct) => `מעלה… ${pct}%`, cuSaving: "שומר בתיקיית התוכנה…",
      cuSyncing: "הקובץ נשמר - מסנכרן את הקטלוג…", cuLive: "הגרסה החדשה זמינה לכל המשתמשים",
      cuSavedHidden: "הקובץ נשמר, אך הסריקה לא הציגה אותו (ייתכן שהוא מוסתר או שהסיומת אינה נסרקת).",
      cuExists: "קובץ בשם זה כבר קיים בתיקייה. סמנו \"החלפה\" כדי להחליף אותו.",
      cuTooLarge: (mb) => `הקובץ גדול מהמותר (${mb} MB)`, cuBadType: (exts) => `ניתן להעלות רק קבצי התקנה (${exts})`,
      cuDoneToast: (name) => `${name} נוסף והקטלוג עודכן`,
      fbSignInTitle: "יש להתחבר כדי לשלוח פנייה",
      fbSignInText: "פניות נשמרות עם פרטי המשתמש המחובר, כדי שנוכל לחזור אליך. התחברו ונסו שוב.",
      annDismiss: "סימון כנקרא", annClose: "סגירה", annLabel: { info: "עדכון", success: "הודעה", warning: "שימו לב", danger: "חשוב" },
    },
    en: {
      docTitle: "PAKAL | Software & Development Portal",
      brand: "PAKAL",
      brandSub: "Software & Development Portal",
      heroBrand: "PAKAL",
      heroTitle: "Software & Development Portal",
      footerCredits: "Built and maintained with ❤️ by the Servers Team",
      themeToggle: "Light/dark mode",
      syncLabel: "Sync / refresh",
      syncDone: (n) => `Catalog synced from the server · ${n} apps`,
      navHome: "Overview",
      navApps: "Software Repository",
      navStacks: "Developer Stacks",
      navPlatforms: "Platforms",
      admin: "Admin",
      search: "Search",
      clearSearch: "Clear search",
      searchPlaceholder: "Search software…",
      heroSearchPlaceholder: "Search by name, version or tag - e.g. python 3.13",
      close: "Close",
      osFilter: "Operating system",
      sortBy: "Sort by",
      osAll: "All operating systems",
      osUniversal: "Universal",
      sortName: "Sort by name",
      sortUpdated: "Recently updated",
      sortSize: "Sort by size",
      coreTools: "Core tools",
      recent: "Recently updated",
      viewAll: "View all",
      download: "Download",
      downloadLatest: "Download latest",
      downloadFor: (os) => `Download for ${os}`,
      downloadAll: "Download all (ZIP)",
      details: "Details",
      tools: (n) => (n === 1 ? "1 tool" : `${n} tools`),
      installers: (n) => (n === 1 ? "1 installer" : `${n} installers`),
      results: (shown, total) => `${shown} of ${total} packages`,
      clearFilters: "Clear filters",
      noResultsTitle: "No matching software",
      noResultsText: "Try a different search term or clear the filters.",
      emptyTitle: "The repository is empty",
      emptyText: "Add a folder per application with installers (exe, msi, iso, zip) - the share is scanned automatically.",
      rootMissingTitle: "Repository share unavailable",
      rootMissingText: "The installer share cannot be reached. Make sure it is mounted into the container.",
      loadErrorTitle: "Failed to load the catalog",
      retry: "Retry",
      officialInstallers: "Official installers",
      colFile: "File",
      colVersion: "Version",
      colOs: "OS",
      colDate: "Date",
      colSize: "Size",
      latest: "latest",
      noVersion: "unversioned",
      bundleCtx: (size, n) => `Full bundle · ${size} · ${n.toLocaleString()} files`,
      latestVersion: "Latest version",
      platformsLbl: "Platforms",
      updated: "Updated",
      totalSize: "Total size",
      homepage: "Homepage",
      missingTools: (n) => `${n} not in repository`,
      moreTools: (n) => `+${n} more`,
      noStackTools: "None of this stack's tools were found in the repository",
      noStacks: "No stacks defined yet. Configure them in the admin console.",
      noPlatforms: "No platforms defined yet. Configure them in the admin console.",
      stackDownloadStart: (n, name) => `Packaging ${n} installers from "${name}" into one ZIP`,
      downloadStarted: (name) => `Download started: ${name}`,
      scanning: "Scanning repository…",
      syncedAt: (time) => `Synced ${time}`,
      noFilesForOs: "No installers for this operating system",
      all: "All",
      stackTools: "Tools",
      stackOs: "Target OS",
      feedbackNav: "Suggest / Report",
      feedbackTitle: "Improvements & Requests",
      feedbackIntro: "Have an idea, hit a bug or missing a tool? Let us know.",
      fbCategory: "Request type",
      fbCat_suggestion: "Improvement suggestion",
      fbCat_bug: "Bug report",
      fbCat_app_request: "New tool / app request",
      fbSubject: "Subject",
      fbSubjectPh: "Short summary",
      fbMessage: "Details",
      fbMessagePh: "Describe what happened, what you expected, or what you need",
      fbSender: "Sender details (filled automatically)",
      fbFullName: "Full name",
      fbAccount: "User ID",
      fbIp: "IP address",
      fbTime: "Timestamp",
      fbGuest: "Guest (not signed in)",
      fbSubmit: "Submit",
      fbSending: "Sending…",
      fbSuccess: "Your request was received successfully",
      fbRequired: "Subject and details are required",
      fbThrottled: "Too many submissions. Please try again in a few minutes.",
      signIn: "Sign in",
      signOut: "Sign out",
      reloginCountdown: (s) => `You signed out. Signing in again automatically in ${s} seconds…`,
      reloginNow: "Sign in now",
      cancel: "Cancel",
      reloginNoSession: "No active Keycloak session was found. You can sign in again at any time.",
      dismiss: "Dismiss",
      ssoFailed: "Keycloak sign-in failed",
      signInTitle: "Sign in to the portal", signInIntro: "Sign in so your requests are linked to your account.",
      signInLdapHint: "Your organizational network username and password", signInSso: "Sign in with SSO", signInOr: "or",
      adUsername: "Username", adUsernamePh: "Enter your username", adPassword: "Password", adPasswordPh: "Enter your password",
      adSignIn: "Sign in", adSigningIn: "Signing in…", adFailed: "Invalid username or password",
      adUnavailable: "The directory service (AD) is unavailable", adThrottled: (s) => `Too many attempts. Try again in ${s} seconds.`,
      signedInAs: (n) => `Welcome, ${n}`, signedOut: "You signed out of the portal",
      signingOut: "Signing out…",
      navActions: "Actions",
      navDocker: "Docker Registry",
      actionsSubtitle: "Self-service tools for the local development infrastructure. Pick a tool to get started.",
      hubBack: "Back to Hub",
      hubNexusTitle: "Nexus Artifacts Uploader",
      hubNexusDesc: "Bulk-publish Python, NPM and PowerShell packages to the local Nexus repositories - even folders with hundreds of files.",
      hubStatusLoading: "Loading settings…", hubStatusError: "Could not load the settings",
      hubNexusNotConfigured: "Nexus is not configured",
      hubUploading: (done, total) => `Uploading · ${done} of ${total}`,
      hubQueued: (n) => (n === 1 ? "1 file in the queue" : `${n} files in the queue`),
      hubSignIn: "Sign in to upload", hubReady: "Ready",
      upIntro: "Drop Python, NPM and PowerShell packages - the target repository is picked from the file extension and can be changed on every row.",
      upDrop: "Drag files or folders here",
      upBrowse: "or click to choose files",
      upLimit: (mb) => `up to ${mb} MB per file`,
      upKind_pypi: "Python (PyPI)", upKind_npm: "NPM", upKind_powershell: "PowerShell",
      upNoRepo: "no repository configured",
      upNotConfigured: "The Nexus connection is not configured yet. Administrators can set it up in the admin console.",
      upSignIn: "Sign in to upload packages. You can already prepare the file list.",
      upConfigError: "Could not load the upload settings",
      upQueue: "Upload queue",
      upColFile: "File", upColSize: "Size", upColTarget: "Target repository", upColStatus: "Status",
      upStatus_pending: "Pending", upStatus_uploading: "Uploading", upStatus_success: "Success", upStatus_failed: "Failed", upStatus_exists: "Already Exists", upStatus_cancelled: "Cancelled",
      upFormats: "Supported formats", upFormatsHint: "What is detected and where it goes",
      upFolder: "Choose folder", upFolderHint: "Scans every sub-folder",
      upFormatsTitle: "Supported formats & auto-detection",
      upFormatsIntro: "The package type and target repository are decided by the file extension. This is what is detected automatically and where each format is published:",
      upFmtColExt: "Extension", upFmtColType: "Package type", upFmtColDesc: "Description", upFmtColRepo: "Target repositories",
      upFmt_whl: "Python wheel - a built package", upFmt_targz: "Python source distribution (sdist)",
      upFmt_tgz: "NPM package tarball (npm pack output)", upFmt_nupkg: "PowerShell module / NuGet package",
      upFmtAlt: (kinds) => `Can also be sent to: ${kinds}`,
      upFmtNoteAuto: "Every file gets an automatic target from its extension - the first repository configured for that type.",
      upFmtNoteOverride: "You can change the target repository on any row, or select several rows and change them all at once.",
      upFmtNoteFolder: "Dropped folders are scanned recursively; files that are not supported packages are skipped.",
      upFmtNoteDupes: "Duplicate files (same name and size) are queued only once.",
      upSelectAll: "Select every file in the current filter", upSelectRow: (name) => `Select ${name}`,
      upSelected: (n) => (n === 1 ? "1 file selected" : `${n} files selected`), upNoneSelected: "Select files to change their target",
      upBulkPlaceholder: "Choose a target repository…", upBulkApply: "Change Target for All Selected",
      upBulkApplied: (n, target) => `Target set to ${target} (${n} files changed)`,
      upBulkSkipped: (n) => `${n} selected files were skipped - their format does not fit that repository or they were already sent`,
      upRemoveSelected: "Remove selected",
      upAbort: "Cancel / Abort Upload", upAborting: "Stopping…",
      upAborted: (done, cancelled, pending) => `Upload stopped: ${done} completed · ${cancelled} cancelled · ${pending} still pending`,
      upCancelledLate: "Cancelled after the file was sent - Nexus may already have published it",
      upIncompatible: "incompatible",
      upOverrideOff: "Changing the target repository is disabled by the administrator",
      upTargetLocked: "The target cannot change once the file was sent",
      upManual: "Manual", upManualHint: (auto) => `Chosen manually · automatic target: ${auto}`,
      upFilterAll: "All", upNoMatch: "No files with this status",
      upShowing: (shown, total) => `Showing ${shown} of ${total}`,
      upShowMore: (n) => `Show More (${n} remaining)`, upShowLess: "Show less",
      upPublishing: "Publishing to Nexus…",
      upPublishedTo: (repo) => `Published to ${repo}`, upExistsIn: (repo) => `This version already exists in ${repo}`,
      upStart: (n) => (n === 1 ? "Upload 1 file" : `Upload ${n} files`),
      upRetry: "Retry failed & cancelled",
      upClearDone: "Clear completed",
      upClearAll: "Clear all",
      upBatch: (done, total) => `${done} of ${total} files`,
      upDone: (s, e, f) => `Upload finished: ${s} succeeded · ${e} already existed · ${f} failed`,
      upUnsupported: "Unsupported file type (.whl .tar.gz .tgz .nupkg)",
      upNoTarget: "No target repository is configured for this package type",
      upTooLarge: (mb) => `File is larger than ${mb} MB`,
      upAdded: (n) => (n === 1 ? "1 file added to the queue" : `${n} files added to the queue`),
      upDuplicates: (n) => `${n} duplicate files skipped`,
      upSkipped: (n) => `${n} files that are not supported packages were skipped`,
      upRemove: "Remove from queue", upCancel: "Cancel upload", upCancelled: "Upload cancelled",
      upNetwork: "Network error - could not reach the server",
      upLeave: "Uploads are still running. Leave the page?",
      cuAdd: "Add version / Upload file", cuAdminOnly: "Admins only",
      cuIntro: (folder) => `The file is saved directly in the application's folder on the server (\u2068${folder}\u2069) and the catalog resyncs for everyone right away.`,
      cuFolder: "Version folder (optional)", cuFolderHint: "Leave empty to save in the application's main folder.",
      cuOverwrite: "Replace the existing file with this name", cuUpload: "Upload to server", cuChoose: "Choose another file",
      cuUploading: (pct) => `Uploading… ${pct}%`, cuSaving: "Saving into the application folder…",
      cuSyncing: "Saved - syncing the catalog…", cuLive: "The new version is live for every user",
      cuSavedHidden: "The file was saved, but the scan did not list it (it may be hidden, or its extension is not scanned).",
      cuExists: "A file with this name already exists in the folder. Tick \"Replace\" to overwrite it.",
      cuTooLarge: (mb) => `The file exceeds the limit (${mb} MB)`, cuBadType: (exts) => `Only installer files can be added (${exts})`,
      cuDoneToast: (name) => `${name} was added and the catalog updated`,
      fbSignInTitle: "Sign in to send a request",
      fbSignInText: "Requests are saved with the signed-in user's details so we can get back to you. Sign in and try again.",
      annDismiss: "Mark as read", annClose: "Close", annLabel: { info: "Update", success: "Notice", warning: "Heads up", danger: "Important" },
    },
  };

  const CATEGORY_FALLBACK = {
    all: { he: "הכל", en: "All" },
    code: { he: "פיתוח", en: "Development" },
    text: { he: "עורכים ומסמכים", en: "Editors & Docs" },
    database: { he: "מסדי נתונים ודאטה", en: "Data & Databases" },
    design: { he: "עיצוב ומדיה", en: "Design & Media" },
    tools: { he: "כלים ותשתית", en: "Tools & Infra" },
  };

  const state = {
    lang: window.PAKAL.loadLang(),
    apps: [],
    appsById: new Map(),
    bundles: [],
    platforms: [],
    categories: [],
    scan: null,
    view: "home",
    category: "all",
    search: "",
    os: "all",
    sort: "name",
    loading: true,
    loadError: null,
    modal: null,
    modalOs: "all",
    pendingAppId: null,
    auth: null,
    relogin: { mode: null, remaining: 0, total: 0, timer: null },
    ui: {},
    announcement: null,
    actions: {
      config: null, error: null, queue: [], seq: 0, running: false, aborting: false, controller: null,
      tool: null, filter: "all", visible: 20, bulkTarget: "",
    },
    dockerBuild: null,
    cardUpload: null,
  };

  // Admin-controlled visibility (console "Portal interface" page); unknown or not-yet-loaded keys count as visible.
  const shown = (key) => state.ui[key] !== false;
  // Server-verified admin (Keycloak admin role, LDAP admin group, or an admin console session).
  const isAdmin = () => Boolean(state.auth && state.auth.admin && state.auth.admin.allowed);
  const viewShown = (view) => VIEWS.includes(view) && (!VIEW_TOGGLES[view] || shown(VIEW_TOGGLES[view]));

  const userOs = (() => {
    const ua = navigator.userAgent || "";
    // Only Windows and Linux exist in this environment; anything else (macOS, phones, tablets) defaults to Windows.
    if (/Windows|Android|iPhone|iPad|iPod|Mac OS X|Macintosh/i.test(ua)) return "Windows";
    if (/Linux|X11/i.test(ua)) return "Linux";
    return "Windows";
  })();

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function t(key, ...args) {
    const value = (I18N[state.lang] && I18N[state.lang][key]) ?? I18N.he[key] ?? key;
    return typeof value === "function" ? value(...args) : value;
  }

  const loc = (obj, field) => obj[`${field}_${state.lang}`] || obj[`${field}_he`] || obj[`${field}_en`] || "";

  function categoryLabel(id) {
    const cat = state.categories.find((c) => c.id === id);
    if (cat) return state.lang === "en" ? cat.label_en : cat.label_he;
    return (CATEGORY_FALLBACK[id] || CATEGORY_FALLBACK.tools)[state.lang];
  }

  const osLabel = (os) => (os === "Universal" ? t("osUniversal") : os);
  const preferredFile = (app) => (app ? (app.latest_by_os && app.latest_by_os[userOs]) || app.latest || null : null);
  const fileSize = (file) => (file ? file.bundle_size_human || file.size_human : "");
  const bdi = (text) => `<bdi>${esc(text)}</bdi>`;

  const versionTag = (version) => (version
    ? `<span class="version-tag">v${esc(version)}</span>`
    : `<span class="version-tag none">${esc(t("noVersion"))}</span>`);
  const sizeTag = (size) => (size ? `<span class="size-tag">${esc(size)}</span>` : "");
  const osTags = (list) => `<span class="os-list">${list.map((os) => `<span class="os-tag">${esc(osLabel(os))}</span>`).join("")}</span>`;
  const downloadAttrs = (file) => `data-action="download" data-url="${esc(file.download_url)}" data-name="${esc(file.filename)}"`;
  const glyphTile = (bundle, size = "") => `<span class="glyph-tile${size ? ` glyph-tile-${size}` : ""}" style="--tint:${esc(bundle.color)}">${icon(bundle.icon)}</span>`;

  async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store", credentials: "same-origin" });
    if (!response.ok) {
      let detail = `${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        if (body && body.detail) detail = body.detail;
      } catch (_) { /* non-JSON body */ }
      throw new Error(detail);
    }
    return response.json();
  }

  function emptyState(title, text, iconName = "package", action = "") {
    return `<div class="empty"><span class="empty-icon">${icon(iconName)}</span><h3>${esc(title)}</h3><p>${esc(text)}</p>${action}</div>`;
  }

  function catalogUnavailable() {
    if (state.loadError) {
      return emptyState(t("loadErrorTitle"), state.loadError, "alert",
        `<button class="btn btn-secondary" type="button" data-action="reload">${icon("refresh")}<span>${esc(t("retry"))}</span></button>`);
    }
    if (state.scan && !state.scan.root_available && state.scan.source !== "none") {
      return emptyState(t("rootMissingTitle"), t("rootMissingText"), "hdd");
    }
    return emptyState(t("emptyTitle"), t("emptyText"), "package");
  }

  function skeletonCards(count) {
    return Array.from({ length: count }, () => `
      <div class="card app-card skeleton" aria-hidden="true">
        <div class="app-card-top"><span class="sk sk-icon"></span><span class="sk-lines"><span class="sk sk-line w60"></span><span class="sk sk-line w40"></span></span></div>
        <span class="sk-lines"><span class="sk sk-line"></span><span class="sk sk-line w80"></span></span>
      </div>`).join("");
  }

  // -------------------------------------------------------------- renderers

  function appCard(app) {
    const file = preferredFile(app);
    return `
      <article class="card app-card" data-action="open-app" data-id="${esc(app.id)}" tabindex="0" role="button" aria-label="${esc(app.name)}">
        <div class="app-card-top">
          ${appIcon(app.icon_url, app.name)}
          <div class="app-card-title">
            <h3 title="${esc(app.name)}">${bdi(app.name)}</h3>
            <div class="meta">${esc(categoryLabel(app.category))}</div>
          </div>
        </div>
        <p class="app-desc">${esc(loc(app, "description"))}</p>
        <div class="app-card-foot">
          ${versionTag((file && file.version) || app.latest_version)}
          ${sizeTag(fileSize(file))}
          <span class="spacer"></span>
          ${osTags(app.platforms)}
          ${file && shown("btn_quick_download") ? `<button class="icon-btn icon-btn-sm" type="button" ${downloadAttrs(file)} title="${esc(t("download"))} ${esc(file.filename)}" aria-label="${esc(t("download"))}">${icon("download")}</button>` : ""}
        </div>
      </article>`;
  }

  function recentRow(app) {
    const file = preferredFile(app);
    return `
      <li class="list-row" data-action="open-app" data-id="${esc(app.id)}" tabindex="0" role="button">
        ${appIcon(app.icon_url, app.name, "sm")}
        <span style="min-width:0">
          <div class="name">${bdi(app.name)}</div>
          <div class="sub">${esc(categoryLabel(app.category))}</div>
        </span>
        ${versionTag((file && file.version) || app.latest_version)}
        <span class="hide-sm">${sizeTag(fileSize(file))}</span>
        <span class="date hide-sm">${esc(app.updated || "")}</span>
        ${file && shown("btn_quick_download") ? `<button class="icon-btn icon-btn-sm" type="button" ${downloadAttrs(file)} title="${esc(t("download"))}" aria-label="${esc(t("download"))}">${icon("download")}</button>` : "<span></span>"}
      </li>`;
  }

  function stackCard(bundle, maxRows = 6) {
    const apps = bundle.apps.map((id) => state.appsById.get(id)).filter(Boolean);
    const rows = [
      ...apps.map((app) => {
        const file = preferredFile(app);
        return `<li class="tool-row" data-action="open-app" data-id="${esc(app.id)}">${appIcon(app.icon_url, app.name, "xs")}<span class="tool-name">${bdi(app.name)}</span><span class="tool-ver">${esc(file && file.version ? file.version : "")}</span></li>`;
      }),
      ...bundle.missing.map((name) => `<li class="tool-row missing"><span class="app-icon app-icon-xs app-icon-letter">–</span><span class="tool-name">${bdi(name)}</span></li>`),
    ];
    const visibleRows = rows.slice(0, maxRows).join("");
    const extra = rows.length - maxRows;
    return `
      <article class="card stack-card">
        <header class="stack-head">
          ${glyphTile(bundle)}
          <div>
            <h3>${esc(loc(bundle, "name"))}</h3>
            <p>${esc(loc(bundle, "description"))}</p>
          </div>
        </header>
        <ul class="tool-list">${visibleRows || `<li class="tool-row missing">${esc(t("noStackTools"))}</li>`}${extra > 0 ? `<li class="tool-row more">${esc(t("moreTools", extra))}</li>` : ""}</ul>
        <footer class="stack-foot">
          <span class="stack-meta">${esc(t("tools", apps.length))} · <span dir="ltr">${esc(bundle.total_size_human)}</span>${bundle.missing.length ? ` · <span class="warn">${esc(t("missingTools", bundle.missing.length))}</span>` : ""}</span>
          <span class="stack-actions">
            <button class="btn btn-ghost btn-sm" type="button" data-action="open-bundle" data-id="${esc(bundle.id)}">${esc(t("details"))}</button>
            ${shown("btn_bundle_zip") ? `<button class="btn btn-primary btn-sm" type="button" data-action="download-bundle" data-id="${esc(bundle.id)}" ${apps.length ? "" : "disabled"}>${icon("download")}<span>${esc(t("downloadAll"))}</span></button>` : ""}
          </span>
        </footer>
      </article>`;
  }

  function platformIcon(p, size = "") {
    return appIcon(p.icon_url, p.name, size);
  }

  function renderHome() {
    const root = $("#home-dynamic");
    if (state.loading) {
      root.innerHTML = `<section class="section"><div class="section-head"><h2 class="section-title">${esc(t("coreTools"))}</h2></div><div class="grid grid-apps">${skeletonCards(4)}</div></section>`;
      return;
    }
    if (!state.apps.length) {
      root.innerHTML = `<section class="section">${catalogUnavailable()}</section>`;
      return;
    }

    let core = state.apps.filter((a) => a.featured);
    if (core.length < 4) {
      const fill = state.apps.filter((a) => !a.featured).sort((a, b) => b.updated_ts - a.updated_ts);
      core = core.concat(fill.slice(0, 4 - core.length));
    }
    core = core.slice(0, 8);
    const recent = [...state.apps].sort((a, b) => b.updated_ts - a.updated_ts).slice(0, 6);

    root.innerHTML = `
      <section class="section">
        <div class="section-head">
          <h2 class="section-title">${esc(t("coreTools"))}</h2>
          <button class="link-btn" type="button" data-action="goto" data-view="apps">${esc(t("viewAll"))}${icon("arrow", "icon-flip")}</button>
        </div>
        <div class="grid grid-apps">${core.map(appCard).join("")}</div>
      </section>
      <section class="section">
        <div class="section-head"><h2 class="section-title">${esc(t("recent"))}</h2></div>
        <ul class="list card list-card">${recent.map(recentRow).join("")}</ul>
      </section>
      ${state.bundles.length && shown("tab_bundles") ? `
      <section class="section">
        <div class="section-head">
          <h2 class="section-title">${esc(t("navStacks"))}<span class="count">${state.bundles.length}</span></h2>
          <button class="link-btn" type="button" data-action="goto" data-view="bundles">${esc(t("viewAll"))}${icon("arrow", "icon-flip")}</button>
        </div>
        <div class="grid grid-stacks">${state.bundles.slice(0, 3).map((b) => stackCard(b, 4)).join("")}</div>
      </section>` : ""}`;
  }

  function filteredApps() {
    const terms = state.search.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const list = state.apps.filter((app) => {
      if (state.category !== "all" && app.category !== state.category) return false;
      if (state.os !== "all" && !app.platforms.includes(state.os)) return false;
      if (!terms.length) return true;
      const haystack = [
        app.name, app.folder, app.description_he, app.description_en, categoryLabel(app.category), ...(app.tags || []),
        ...app.files.map((f) => `${f.filename} ${f.version || ""}`),
      ].join(" ").toLowerCase();
      return terms.every((term) => haystack.includes(term));
    });
    const sorters = {
      name: (a, b) => a.name.localeCompare(b.name, state.lang, { sensitivity: "base" }),
      updated: (a, b) => b.updated_ts - a.updated_ts,
      size: (a, b) => b.total_size_bytes - a.total_size_bytes,
    };
    return list.sort(sorters[state.sort] || sorters.name);
  }

  function renderToolbar() {
    const osOptions = [["all", t("osAll")], ["Windows", "Windows"], ["Linux", "Linux"]];
    $("#os-filter").innerHTML = osOptions.map(([v, label]) => `<option value="${v}" ${state.os === v ? "selected" : ""}>${esc(label)}</option>`).join("");
    const sortOptions = [["name", t("sortName")], ["updated", t("sortUpdated")], ["size", t("sortSize")]];
    $("#sort-select").innerHTML = sortOptions.map(([v, label]) => `<option value="${v}" ${state.sort === v ? "selected" : ""}>${esc(label)}</option>`).join("");
  }

  function renderPills() {
    const counts = {};
    state.apps.forEach((a) => { counts[a.category] = (counts[a.category] || 0) + 1; });
    const cats = (state.categories.length ? state.categories : [{ id: "all" }])
      .filter((c) => c.id === "all" || counts[c.id]);
    $("#category-pills").innerHTML = cats.map((c) => {
      const count = c.id === "all" ? state.apps.length : counts[c.id] || 0;
      const active = state.category === c.id;
      return `<button class="pill ${active ? "active" : ""}" type="button" role="tab" aria-selected="${active}" data-action="category" data-category="${esc(c.id)}"><span>${esc(categoryLabel(c.id))}</span><span class="pill-count">${count}</span></button>`;
    }).join("");
  }

  function renderApps() {
    renderPills();
    const grid = $("#apps-grid");
    const line = $("#results-line");
    if (state.loading) {
      line.innerHTML = "";
      grid.innerHTML = skeletonCards(8);
      return;
    }
    if (!state.apps.length) {
      line.innerHTML = "";
      grid.innerHTML = catalogUnavailable();
      return;
    }
    const list = filteredApps();
    const filtered = state.search.trim() || state.os !== "all" || state.category !== "all";
    line.innerHTML = `<span>${esc(t("results", list.length, state.apps.length))}</span>${filtered ? `<button class="link-btn" type="button" data-action="clear-filters">${icon("x")}${esc(t("clearFilters"))}</button>` : ""}`;
    grid.innerHTML = list.length
      ? list.map(appCard).join("")
      : emptyState(t("noResultsTitle"), t("noResultsText"), "search",
        `<button class="btn btn-secondary" type="button" data-action="clear-filters">${esc(t("clearFilters"))}</button>`);
  }

  function renderBundles() {
    const grid = $("#bundles-grid");
    if (state.loading) {
      grid.innerHTML = skeletonCards(3);
      return;
    }
    grid.innerHTML = state.bundles.length
      ? state.bundles.map((b) => stackCard(b)).join("")
      : emptyState(t("navStacks"), t("noStacks"), "layers");
  }

  function renderPlatforms() {
    const grid = $("#platforms-grid");
    grid.innerHTML = state.platforms.length
      ? state.platforms.map((p) => `
        <a class="card platform-card" href="${esc(p.url)}" target="_blank" rel="noopener noreferrer">
          ${platformIcon(p)}
          <span class="platform-body">
            <strong>${esc(p.name)}</strong>
            <span class="muted">${esc(loc(p, "description"))}</span>
            <span class="platform-url">${esc(p.url.replace(/^https?:\/\//, ""))}</span>
          </span>
          <span class="platform-ext">${icon("external")}</span>
        </a>`).join("")
      : emptyState(t("navPlatforms"), t("noPlatforms"), "globe");
  }

  // ---------------------------------------------------------- actions: hub

  const ACTION_TOOLS = ["nexus", "docker"];
  const actionsHash = () => (state.actions.tool ? `actions/${state.actions.tool}` : "actions");

  function hubCard({ tool, title, desc, iconName, chips, status, tone, disabled = false, english = false }) {
    return `
      <button class="hub-card hub-card-${tool}" type="button" data-action="hub-open" data-tool="${tool}" ${disabled ? "disabled" : ""} ${english ? 'dir="ltr" lang="en"' : ""}>
        <span class="hub-card-top">
          <span class="hub-icon">${icon(iconName)}</span>
          <span class="hub-go" aria-hidden="true">${icon("arrow", "icon-flip")}</span>
        </span>
        <span class="hub-card-body">
          <strong class="hub-title">${esc(title)}</strong>
          <span class="hub-desc">${esc(desc)}</span>
        </span>
        <span class="hub-chips">${chips.map((c) => `<span class="hub-chip">${esc(c)}</span>`).join("")}</span>
        <span class="hub-status tone-${tone}"><span class="hub-dot"></span><span>${esc(status)}</span></span>
      </button>`;
  }

  function nexusHubStatus() {
    const a = state.actions;
    const cfg = a.config;
    if (!cfg) return a.error ? [t("hubStatusError"), "bad"] : [t("hubStatusLoading"), "muted"];
    if (!cfg.configured) return [t("hubNexusNotConfigured"), "warn"];
    if (a.running || a.aborting) {
      const { finished, count } = batchProgress();
      return [t("hubUploading", finished, count), "busy"];
    }
    if (a.queue.length) return [t("hubQueued", a.queue.length), "info"];
    if (!cfg.authenticated) return [t("hubSignIn"), "warn"];
    return [t("hubReady"), "ok"];
  }

  // The Docker card is English-only like the rest of the Docker ecosystem; docker.js reports its state.
  function dockerHubCard() {
    if (!shown("docker_build")) return "";
    const d = state.dockerBuild;
    if (d && d.loaded && !d.visible) return "";
    const [status, tone] = d && d.loaded ? [d.status, d.tone] : ["Checking availability…", "muted"];
    return hubCard({
      tool: "docker",
      title: "Docker Image Builder",
      desc: "Upload a project ZIP with a Dockerfile - the server builds the image, tags it and pushes it to the organizational registry.",
      iconName: "container",
      chips: ["Dockerfile", "Build", "Push", "Live log"],
      status,
      tone,
      disabled: Boolean(d && d.loaded && !d.available),
      english: true,
    });
  }

  function renderHub() {
    const grid = $("#hub-grid");
    if (!grid) return;
    const cfg = state.actions.config;
    const [status, tone] = nexusHubStatus();
    const kinds = cfg ? Object.keys(cfg.kinds).map((k) => t(`upKind_${k}`)) : [t("upKind_pypi"), t("upKind_npm"), t("upKind_powershell")];
    grid.innerHTML = hubCard({
      tool: "nexus",
      title: t("hubNexusTitle"),
      desc: t("hubNexusDesc"),
      iconName: "upload",
      chips: kinds,
      status,
      tone,
    }) + dockerHubCard();
  }

  function renderActionsPanels() {
    const tool = state.actions.tool;
    $$("#view-actions .actions-panel").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== (tool || "hub");
    });
    if (!tool) renderHub();
  }

  function openTool(tool, { push = false } = {}) {
    const a = state.actions;
    const next = ACTION_TOOLS.includes(tool) && (tool !== "docker" || shown("docker_build")) ? tool : null;
    const changed = next !== a.tool;
    a.tool = next;
    if (state.view === "actions" && window.location.hash !== `#${actionsHash()}`) {
      if (push && next) history.pushState({ pakalTool: next }, "", `#${actionsHash()}`);
      else history.replaceState(null, "", `#${actionsHash()}`);
    }
    renderActionsPanels();
    if (changed) window.scrollTo({ top: 0 });
    emit("actions-tool", a.tool);
  }

  function backToHub() {
    if (history.state && history.state.pakalTool) history.back();
    else openTool(null);
  }

  // ------------------------------------------------- actions: Nexus artifacts uploader

  const KIND_ICONS = { pypi: "code", npm: "package", powershell: "terminal" };
  const STATUS_BADGES = {
    pending: "badge-neutral", uploading: "badge-accent", success: "badge-success", exists: "badge-warn", failed: "badge-danger", cancelled: "badge-neutral",
  };
  const STATUSES = ["pending", "uploading", "success", "exists", "failed", "cancelled"];
  const FINISHED = new Set(["success", "exists", "failed", "cancelled"]);
  const EDITABLE = new Set(["pending", "failed", "cancelled"]);
  const QUEUE_PAGE = 20;
  const FORMAT_KEYS = { ".whl": "upFmt_whl", ".tar.gz": "upFmt_targz", ".tgz": "upFmt_tgz", ".nupkg": "upFmt_nupkg" };

  function humanBytes(n) {
    if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(2)} GB`;
    if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(1)} MB`;
    if (n >= 1024) return `${Math.round(n / 1024)} KB`;
    return `${n} B`;
  }

  function detectKind(name) {
    const cfg = state.actions.config;
    const lower = name.toLowerCase();
    const rule = ((cfg && cfg.detect) || []).find(([ext]) => lower.endsWith(ext));
    return rule ? rule[1] : null;
  }

  // Every "kind:repository" the file's format can be published to; the first entry is the automatic target.
  function compatibleTargets(name) {
    const cfg = state.actions.config;
    const detected = detectKind(name);
    if (!cfg || !detected) return [];
    const lower = name.toLowerCase();
    const kinds = Object.keys(cfg.kinds).sort((a, b) => (a === detected ? -1 : b === detected ? 1 : 0));
    return kinds.flatMap((kind) => (cfg.kinds[kind].extensions.some((ext) => lower.endsWith(ext))
      ? cfg.kinds[kind].repositories.map((repo) => `${kind}:${repo}`) : []));
  }

  // What the user may pick: everything compatible, or only the automatic target when overrides are disabled.
  function targetsFor(name) {
    const targets = compatibleTargets(name);
    return state.actions.config.repo_override ? targets : targets.slice(0, 1);
  }

  const splitTarget = (target) => [target.slice(0, target.indexOf(":")), target.slice(target.indexOf(":") + 1)];
  const targetLabel = (target) => { const [kind, repo] = splitTarget(target); return `${t(`upKind_${kind}`)} · ${repo}`; };
  const findQueued = (id) => state.actions.queue.find((i) => i.id === id);
  const itemPct = (item) => (item.size ? Math.min(100, Math.round((100 * item.loaded) / item.size)) : 0);
  const canRetarget = (item) => Boolean(state.actions.config.repo_override) && !item.blocked && EDITABLE.has(item.status);

  function uploadCounts() {
    const counts = Object.fromEntries(STATUSES.map((s) => [s, 0]));
    state.actions.queue.forEach((i) => { counts[i.status] += 1; });
    return counts;
  }

  function batchProgress() {
    let total = 0;
    let done = 0;
    let finished = 0;
    let count = 0;
    state.actions.queue.forEach((i) => {
      if (i.blocked) return;
      count += 1;
      total += i.size;
      if (FINISHED.has(i.status)) {
        done += i.size;
        finished += 1;
      } else if (i.status === "uploading") done += Math.min(i.loaded, i.size);
    });
    return { pct: total ? Math.round((100 * done) / total) : 0, finished, count };
  }

  function filteredQueue() {
    const { queue, filter } = state.actions;
    return filter === "all" ? queue : queue.filter((i) => i.status === filter);
  }

  function targetCell(item) {
    if (item.blocked || !item.target) return `<span class="muted">—</span>`;
    const cfg = state.actions.config;
    const compatible = compatibleTargets(item.name);
    const allowed = new Set(targetsFor(item.name));
    const editable = canRetarget(item);
    const [kind] = splitTarget(item.target);
    const groups = Object.entries(cfg.kinds).filter(([, meta]) => meta.repositories.length).map(([k, meta]) => `
      <optgroup label="${esc(t(`upKind_${k}`))}">${meta.repositories.map((repo) => {
        const value = `${k}:${repo}`;
        const ok = allowed.has(value) || value === item.target;
        return `<option value="${esc(value)}"${value === item.target ? " selected" : ""}${ok ? "" : " disabled"}>${esc(repo)}${compatible.includes(value) ? "" : ` (${esc(t("upIncompatible"))})`}</option>`;
      }).join("")}</optgroup>`).join("");
    const title = editable ? targetLabel(item.target)
      : !cfg.repo_override ? t("upOverrideOff") : t("upTargetLocked");
    const manual = compatible.length && item.target !== compatible[0];
    return `
      <div class="q-target-cell">
        <span class="q-kind" title="${esc(t(`upKind_${kind}`))}">${icon(KIND_ICONS[kind])}</span>
        <select class="select select-sm q-select${item.flash ? " is-flash" : ""}${manual ? " is-manual" : ""}" data-qid="${item.id}" dir="ltr" aria-label="${esc(t("upColTarget"))}: ${esc(item.name)}" title="${esc(title)}" ${editable ? "" : "disabled"}>${groups}</select>
        ${manual ? `<span class="q-manual" title="${esc(t("upManualHint", targetLabel(compatible[0])))}">${esc(t("upManual"))}</span>` : ""}
      </div>`;
  }

  function queueRow(item) {
    const pct = itemPct(item);
    const detail = item.status === "uploading" && item.publishing ? t("upPublishing") : item.detail;
    const action = item.status === "uploading"
      ? `<button class="icon-btn icon-btn-sm" type="button" data-action="upload-cancel" data-qid="${item.id}" title="${esc(t("upCancel"))}" aria-label="${esc(t("upCancel"))}">${icon("x")}</button>`
      : `<button class="icon-btn icon-btn-sm" type="button" data-action="upload-remove" data-qid="${item.id}" title="${esc(t("upRemove"))}" aria-label="${esc(t("upRemove"))}">${icon("trash")}</button>`;
    return `
      <tr class="q-row q-${item.status}${item.selected ? " is-selected" : ""}${item.flash ? " is-flash" : ""}" data-qid="${item.id}">
        <td class="q-check"><input type="checkbox" class="check" data-qsel="${item.id}" ${item.selected ? "checked" : ""} aria-label="${esc(t("upSelectRow", item.name))}"></td>
        <td><div class="file-cell">
          <span class="file-name" dir="ltr" title="${esc(item.name)}">${esc(item.name)}</span>
          ${item.pkg ? `<span class="file-ctx" dir="ltr">${esc(item.pkg)}</span>` : ""}
          ${detail ? `<span class="q-detail">${esc(detail)}</span>` : ""}
        </div></td>
        <td class="num">${esc(humanBytes(item.size))}</td>
        <td>${targetCell(item)}</td>
        <td class="q-status-cell">
          <span class="badge ${STATUS_BADGES[item.status]}">${item.status === "uploading" ? `<span class="status-dot busy"></span>` : ""}${esc(t(`upStatus_${item.status}`))}</span>
          ${item.status === "uploading" ? `<span class="q-progress" aria-hidden="true"><span style="width:${pct}%"></span></span><span class="q-pct">${pct}%</span>` : ""}
        </td>
        <td class="actions-cell">${action}</td>
      </tr>`;
  }

  function queueHead() {
    const a = state.actions;
    const counts = uploadCounts();
    const filters = [["all", a.queue.length], ...STATUSES.filter((s) => counts[s]).map((s) => [s, counts[s]])];
    const chips = filters.map(([key, n]) => `
      <button class="q-filter${a.filter === key ? " active" : ""}" type="button" data-action="queue-filter" data-filter="${key}" aria-pressed="${a.filter === key}">
        ${key === "all" ? "" : `<span class="q-filter-dot q-dot-${key}"></span>`}<span>${esc(key === "all" ? t("upFilterAll") : t(`upStatus_${key}`))}</span><span class="q-filter-n">${n}</span>
      </button>`).join("");
    const { pct, finished, count } = batchProgress();
    return `
      <div class="queue-head">
        <div class="queue-title">
          <h3>${esc(t("upQueue"))} <span class="subtle mono">${a.queue.length}</span></h3>
          <div class="queue-chips" role="group" aria-label="${esc(t("upColStatus"))}">${chips}</div>
        </div>
      </div>
      <div class="batch${a.running || a.aborting ? " is-running" : ""}">
        <div class="batch-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}"><span id="batch-fill" style="width:${pct}%"></span></div>
        <span class="batch-text" id="batch-text">${pct}% · ${esc(t("upBatch", finished, count))}</span>
      </div>`;
  }

  function queueTools() {
    const a = state.actions;
    const cfg = a.config;
    const counts = uploadCounts();
    const pending = a.queue.filter((i) => i.status === "pending" && !i.blocked);
    const selected = a.queue.filter((i) => i.selected);
    const retargetable = selected.filter(canRetarget);
    const retryable = a.queue.some((i) => (i.status === "failed" || i.status === "cancelled") && !i.blocked);
    const canUpload = cfg.configured && cfg.authenticated;
    const bulkTargets = [...new Set(retargetable.flatMap((i) => targetsFor(i.name)))];
    if (a.bulkTarget && !bulkTargets.includes(a.bulkTarget)) a.bulkTarget = "";
    const bulk = cfg.repo_override ? `
      <div class="q-bulk${selected.length ? " has-selection" : ""}">
        <select class="select select-sm" id="bulk-target" dir="ltr" aria-label="${esc(t("upBulkPlaceholder"))}" ${bulkTargets.length ? "" : "disabled"}>
          <option value="">${esc(t("upBulkPlaceholder"))}</option>
          ${bulkTargets.map((o) => `<option value="${esc(o)}"${o === a.bulkTarget ? " selected" : ""}>${esc(targetLabel(o))}</option>`).join("")}
        </select>
        <button class="btn btn-secondary btn-sm" type="button" data-action="bulk-apply" ${a.bulkTarget && retargetable.length ? "" : "disabled"}>${icon("check")}<span>${esc(t("upBulkApply"))}</span></button>
      </div>` : "";
    const primary = a.running || a.aborting
      ? `<button class="btn btn-danger" type="button" data-action="upload-abort" ${a.aborting ? "disabled" : ""}>${a.aborting ? '<span class="dk-spinner"></span>' : icon("stop")}<span>${esc(a.aborting ? t("upAborting") : t("upAbort"))}</span></button>`
      : `<button class="btn btn-primary" type="button" data-action="upload-start" ${pending.length && canUpload ? "" : "disabled"}>${icon("upload")}<span>${esc(t("upStart", pending.length))}</span></button>`;
    return `
      <div class="q-toolbar">
        <div class="q-selection">
          <span class="q-selected-count">${esc(selected.length ? t("upSelected", selected.length) : t("upNoneSelected"))}</span>
          ${bulk}
          ${selected.length && !a.running ? `<button class="btn btn-ghost btn-sm" type="button" data-action="queue-remove-selected">${icon("trash")}<span>${esc(t("upRemoveSelected"))}</span></button>` : ""}
        </div>
        <div class="queue-actions">
          ${retryable && !a.running ? `<button class="btn btn-secondary btn-sm" type="button" data-action="upload-retry">${icon("refresh")}<span>${esc(t("upRetry"))}</span></button>` : ""}
          ${counts.success + counts.exists ? `<button class="btn btn-ghost btn-sm" type="button" data-action="upload-clear-done">${icon("check")}<span>${esc(t("upClearDone"))}</span></button>` : ""}
          <button class="btn btn-ghost btn-sm" type="button" data-action="upload-clear-all" ${a.running || a.aborting ? "disabled" : ""}>${icon("trash")}<span>${esc(t("upClearAll"))}</span></button>
          ${primary}
        </div>
      </div>`;
  }

  function queueMore(list) {
    const a = state.actions;
    const remaining = list.length - Math.min(a.visible, list.length);
    return `
      <span class="q-showing">${esc(t("upShowing", Math.min(a.visible, list.length), list.length))}</span>
      <span class="q-more-actions">
        ${a.visible > QUEUE_PAGE ? `<button class="btn btn-ghost btn-sm" type="button" data-action="queue-less">${icon("up")}<span>${esc(t("upShowLess"))}</span></button>` : ""}
        ${remaining > 0 ? `<button class="btn btn-secondary btn-sm" type="button" data-action="queue-more">${icon("down")}<span>${esc(t("upShowMore", remaining))}</span></button>` : ""}
      </span>`;
  }

  // Rewrites only when the markup changed, so an open dropdown survives unrelated progress updates.
  const lastHtml = new WeakMap();
  function setHtml(el, html) {
    if (el && lastHtml.get(el) !== html) {
      el.innerHTML = html;
      lastHtml.set(el, html);
    }
  }

  function syncSelectAll() {
    const box = $("#q-select-all");
    if (!box) return;
    const list = filteredQueue();
    const picked = list.filter((i) => i.selected).length;
    box.checked = Boolean(list.length) && picked === list.length;
    box.indeterminate = picked > 0 && picked < list.length;
  }

  function renderQueueChrome() {
    setHtml($("#queue-head"), queueHead());
    setHtml($("#queue-tools"), queueTools());
    syncSelectAll();
    if (!state.actions.tool) renderHub();
  }

  function renderQueueBody() {
    const body = $("#queue-body");
    if (!body) return;
    const list = filteredQueue();
    const rows = list.slice(0, state.actions.visible);
    body.innerHTML = rows.length ? rows.map(queueRow).join("") : `<tr><td colspan="6" class="muted center">${esc(t("upNoMatch"))}</td></tr>`;
    const more = $("#queue-more");
    if (more) {
      more.innerHTML = queueMore(list);
      more.hidden = list.length <= QUEUE_PAGE && state.actions.visible <= QUEUE_PAGE;
    }
  }

  function renderQueue() {
    const a = state.actions;
    if (a.filter !== "all" && !a.queue.some((i) => i.status === a.filter)) a.filter = "all";
    if (!a.queue.length || !$("#queue-card")) {
      renderActions();
      return;
    }
    renderQueueChrome();
    renderQueueBody();
  }

  function renderActions() {
    renderActionsPanels();
    const root = $("#actions-root");
    const a = state.actions;
    const cfg = a.config;
    if (!cfg) {
      root.innerHTML = a.error
        ? emptyState(t("upConfigError"), a.error, "alert", `<button class="btn btn-secondary" type="button" data-action="actions-reload">${icon("refresh")}<span>${esc(t("retry"))}</span></button>`)
        : `<div class="card uploader uploader-loading" aria-hidden="true"></div>`;
      return;
    }
    let notice = "";
    if (!cfg.configured) notice = `<div class="notice">${icon("alert")}<span>${esc(t("upNotConfigured"))}</span></div>`;
    else if (!cfg.authenticated) {
      notice = `<div class="notice notice-row">${icon("lock")}<span>${esc(t("upSignIn"))}</span><button class="btn btn-secondary btn-sm" type="button" data-action="login">${icon("login")}<span>${esc(t("signIn"))}</span></button></div>`;
    }
    const disabled = !cfg.configured;
    root.innerHTML = `
      ${notice}
      <section class="card uploader nx-drop-card">
        <div class="nx-drop-row">
          <div class="dropzone${disabled ? " disabled" : ""}" id="dropzone" role="button" tabindex="0" data-action="pick-packages" aria-disabled="${disabled}">
            <span class="dropzone-icon">${icon("upload")}</span>
            <strong>${esc(t("upDrop"))}</strong>
            <span>${esc(t("upBrowse"))}${cfg.max_upload_mb ? ` · ${esc(t("upLimit", cfg.max_upload_mb))}` : ""}</span>
          </div>
          <div class="nx-side">
            <button class="nx-side-btn" type="button" data-action="upload-formats">
              <span class="nx-side-icon">${icon("info")}</span>
              <span class="nx-side-text"><strong>${esc(t("upFormats"))}</strong><span>${esc(t("upFormatsHint"))}</span></span>
            </button>
            <button class="nx-side-btn" type="button" data-action="pick-folder" ${disabled ? "disabled" : ""}>
              <span class="nx-side-icon">${icon("folder")}</span>
              <span class="nx-side-text"><strong>${esc(t("upFolder"))}</strong><span>${esc(t("upFolderHint"))}</span></span>
            </button>
          </div>
        </div>
      </section>
      ${a.queue.length ? `
      <section class="card uploader-queue" id="queue-card">
        <div id="queue-head"></div>
        <div id="queue-tools"></div>
        <div class="table-wrap q-wrap">
          <table class="table queue-table">
            <thead><tr>
              <th class="q-check"><input type="checkbox" class="check" id="q-select-all" aria-label="${esc(t("upSelectAll"))}" title="${esc(t("upSelectAll"))}"></th>
              <th>${esc(t("upColFile"))}</th><th>${esc(t("upColSize"))}</th><th>${esc(t("upColTarget"))}</th><th>${esc(t("upColStatus"))}</th><th></th>
            </tr></thead>
            <tbody id="queue-body"></tbody>
          </table>
        </div>
        <div class="q-more" id="queue-more" hidden></div>
      </section>` : ""}`;
    if (a.queue.length) {
      renderQueueChrome();
      renderQueueBody();
    } else if (!a.tool) renderHub();
  }

  function formatsModal() {
    const cfg = state.actions.config;
    if (!cfg) return "";
    const rows = cfg.detect.map(([ext, kind]) => {
      const alt = Object.keys(cfg.kinds).filter((k) => k !== kind && cfg.kinds[k].extensions.includes(ext));
      const repos = cfg.kinds[kind].repositories;
      return `
        <tr>
          <td><code class="fmt-ext" dir="ltr">${esc(ext)}</code></td>
          <td><span class="q-target">${icon(KIND_ICONS[kind])}<span>${esc(t(`upKind_${kind}`))}</span></span></td>
          <td>${esc(t(FORMAT_KEYS[ext] || ""))}${alt.length ? `<span class="fmt-alt">${esc(t("upFmtAlt", alt.map((k) => t(`upKind_${k}`)).join(", ")))}</span>` : ""}</td>
          <td><span class="fmt-repos" dir="ltr">${repos.length ? esc(repos.join(", ")) : `<span class="muted">${esc(t("upNoRepo"))}</span>`}</span></td>
        </tr>`;
    }).join("");
    const notes = [
      t("upFmtNoteAuto"),
      cfg.repo_override ? t("upFmtNoteOverride") : t("upOverrideOff"),
      t("upFmtNoteFolder"),
      t("upFmtNoteDupes"),
      cfg.max_upload_mb ? t("upLimit", cfg.max_upload_mb) : "",
    ].filter(Boolean);
    return `
      <div class="modal-header">
        <span class="fmt-glyph">${icon("info")}</span>
        <div class="modal-heading">
          <h2 id="modal-title">${esc(t("upFormatsTitle"))}</h2>
        </div>
      </div>
      <p class="modal-desc">${esc(t("upFormatsIntro"))}</p>
      <div class="table-wrap">
        <table class="table fmt-table">
          <thead><tr><th>${esc(t("upFmtColExt"))}</th><th>${esc(t("upFmtColType"))}</th><th>${esc(t("upFmtColDesc"))}</th><th>${esc(t("upFmtColRepo"))}</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <ul class="fmt-notes">${notes.map((n) => `<li>${icon("check")}<span>${esc(n)}</span></li>`).join("")}</ul>`;
  }

  let progressFrame = 0;

  // Byte progress arrives many times per second; repaint at most once per frame and only what changed.
  function scheduleProgress() {
    if (progressFrame) return;
    progressFrame = requestAnimationFrame(() => {
      progressFrame = 0;
      state.actions.queue.forEach((item) => {
        if (item.status !== "uploading") return;
        const pct = itemPct(item);
        if (pct >= 100 && !item.publishing) {
          item.publishing = true;
          updateRow(item);
          return;
        }
        const row = $(`#queue-body tr[data-qid="${item.id}"]`);
        if (!row) return;
        const bar = $(".q-progress > span", row);
        const label = $(".q-pct", row);
        if (bar) bar.style.width = `${pct}%`;
        if (label) label.textContent = `${pct}%`;
      });
      const { pct, finished, count } = batchProgress();
      const fill = $("#batch-fill");
      const text = $("#batch-text");
      if (fill) {
        fill.style.width = `${pct}%`;
        fill.parentElement.setAttribute("aria-valuenow", String(pct));
      }
      if (text) text.textContent = `${pct}% · ${t("upBatch", finished, count)}`;
    });
  }

  function updateRow(item) {
    const row = $(`#queue-body tr[data-qid="${item.id}"]`);
    if (row) row.outerHTML = queueRow(item);
    renderQueueChrome();
  }

  async function collectDropped(dataTransfer) {
    // DataTransfer entries must be read synchronously, before the first await.
    const entries = Array.from(dataTransfer.items || [])
      .map((item) => (item.kind === "file" && item.webkitGetAsEntry ? item.webkitGetAsEntry() : null))
      .filter(Boolean);
    if (!entries.some((entry) => entry.isDirectory)) return { files: Array.from(dataTransfer.files || []), fromFolder: false };
    const files = [];
    const walk = async (entry, depth) => {
      if (entry.isFile) {
        try { files.push(await new Promise((resolve, reject) => entry.file(resolve, reject))); } catch (_) { /* unreadable */ }
        return;
      }
      if (!entry.isDirectory || depth > 6) return;
      const reader = entry.createReader();
      for (;;) {
        const batch = await new Promise((resolve, reject) => reader.readEntries(resolve, reject)).catch(() => []);
        if (!batch.length) break;
        for (const child of batch) await walk(child, depth + 1);
      }
    };
    for (const entry of entries) await walk(entry, 0);
    return { files, fromFolder: true };
  }

  function addPackages(files, { fromFolder = false } = {}) {
    const a = state.actions;
    const cfg = a.config;
    if (!cfg || !cfg.configured) return;
    const keys = new Set(a.queue.map((i) => `${i.name}|${i.size}`));
    const maxBytes = (cfg.max_upload_mb || 0) * 1024 * 1024;
    let added = 0;
    let duplicates = 0;
    let skipped = 0;
    files.forEach((file) => {
      const key = `${file.name}|${file.size}`;
      if (keys.has(key)) {
        duplicates += 1;
        return;
      }
      const kind = detectKind(file.name);
      if (!kind && fromFolder) {
        skipped += 1;
        return;
      }
      const targets = targetsFor(file.name);
      const item = {
        id: ++a.seq, file, name: file.name, size: file.size, target: targets[0] || "", status: "pending",
        loaded: 0, detail: "", pkg: "", blocked: false, publishing: false, xhr: null, controller: null, selected: false, flash: false,
      };
      const block = (reason) => { item.status = "failed"; item.blocked = true; item.detail = reason; };
      if (!kind) block(t("upUnsupported"));
      else if (!targets.length) block(t("upNoTarget"));
      else if (maxBytes && file.size > maxBytes) block(t("upTooLarge", cfg.max_upload_mb));
      a.queue.push(item);
      keys.add(key);
      added += 1;
    });
    renderQueue();
    if (added) toast(t("upAdded", added), "info", 2200);
    if (duplicates) toast(t("upDuplicates", duplicates), "info", 3000);
    if (skipped) toast(t("upSkipped", skipped), "info", 3500);
    if (a.running) pumpUploads();
  }

  function startUploads() {
    const a = state.actions;
    const cfg = a.config;
    if (!cfg || !cfg.configured || !cfg.authenticated || a.running || a.aborting) return;
    a.running = true;
    a.controller = new AbortController();
    renderQueueChrome();
    pumpUploads();
  }

  function pumpUploads() {
    const a = state.actions;
    if (!a.running) return;
    let free = UPLOAD_CONCURRENCY - a.queue.filter((i) => i.status === "uploading").length;
    for (const item of a.queue) {
      if (free <= 0) break;
      if (item.status === "pending" && !item.blocked && item.target) {
        sendPackage(item);
        free -= 1;
      }
    }
    if (!a.queue.some((i) => i.status === "uploading")) finishBatch();
  }

  function finishBatch() {
    const a = state.actions;
    a.running = false;
    a.controller = null;
    const counts = { success: 0, exists: 0, failed: 0 };
    a.queue.forEach((i) => { if (!i.blocked && counts[i.status] !== undefined) counts[i.status] += 1; });
    renderQueue();
    toast(t("upDone", counts.success, counts.exists, counts.failed), counts.failed ? "error" : "success", 6000);
  }

  // Stops the whole batch: aborting the controller tears down every in-flight request; queued files stay pending.
  function abortUploads() {
    const a = state.actions;
    if (!a.running) return;
    a.running = false;
    a.aborting = true;
    const controller = a.controller;
    a.controller = null;
    renderQueueChrome();
    if (controller) controller.abort();
    if (!a.queue.some((i) => i.status === "uploading")) finishAbort();
  }

  function finishAbort() {
    const a = state.actions;
    if (!a.aborting) return;
    a.aborting = false;
    const counts = uploadCounts();
    renderQueue();
    toast(t("upAborted", counts.success + counts.exists, counts.cancelled, counts.pending), "info", 6000);
  }

  function sendPackage(item) {
    const [kind, repository] = splitTarget(item.target);
    Object.assign(item, { status: "uploading", loaded: 0, detail: "", pkg: "", publishing: false });
    const xhr = new XMLHttpRequest();
    const controller = new AbortController();
    item.xhr = xhr;
    item.controller = controller;
    const batch = state.actions.controller;
    if (batch) batch.signal.addEventListener("abort", () => controller.abort(), { once: true });
    controller.signal.addEventListener("abort", () => { if (item.xhr === xhr) xhr.abort(); }, { once: true });
    xhr.open("PUT", `/api/actions/upload?${new URLSearchParams({ kind, repository, filename: item.name })}`);
    xhr.setRequestHeader("X-PAKAL-Request", "1");
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.responseType = "json";
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) item.loaded = event.loaded;
      scheduleProgress();
    };
    xhr.onload = () => {
      const body = xhr.response || {};
      if (xhr.status === 201) settleUpload(item, "success", body);
      else if (xhr.status === 409) settleUpload(item, "exists", body);
      else {
        if (xhr.status === 401) state.actions.config.authenticated = false;
        const detail = Array.isArray(body.detail) ? body.detail.map((d) => d.msg).join(" · ") : body.detail;
        settleUpload(item, "failed", body, detail || `HTTP ${xhr.status}`);
      }
    };
    xhr.onerror = () => settleUpload(item, "failed", null, t("upNetwork"));
    xhr.onabort = () => settleUpload(item, "cancelled", null, item.publishing ? t("upCancelledLate") : t("upCancelled"));
    xhr.send(item.file);
    updateRow(item);
  }

  function settleUpload(item, status, body, detail = "") {
    if (item.status !== "uploading") return;
    Object.assign(item, { status, xhr: null, controller: null, loaded: status === "cancelled" ? 0 : item.size, publishing: false });
    if (body && body.package) item.pkg = `${body.package} ${body.version || ""}`.trim();
    const repo = splitTarget(item.target)[1];
    if (!detail && status === "success") detail = t("upPublishedTo", repo);
    else if (!detail && status === "exists") detail = t("upExistsIn", repo);
    item.detail = detail || (body && typeof body.detail === "string" ? body.detail : "");
    if (findQueued(item.id)) updateRow(item);
    const a = state.actions;
    if (a.aborting) {
      if (!a.queue.some((i) => i.status === "uploading")) finishAbort();
      return;
    }
    pumpUploads();
  }

  function removeQueued(id) {
    const item = findQueued(id);
    if (!item || item.status === "uploading") return;
    state.actions.queue = state.actions.queue.filter((i) => i.id !== id);
    renderQueue();
  }

  function retryFailed() {
    state.actions.queue.forEach((i) => {
      if ((i.status === "failed" || i.status === "cancelled") && !i.blocked) Object.assign(i, { status: "pending", detail: "", loaded: 0 });
    });
    renderQueue();
    startUploads();
  }

  function setSelected(ids, on) {
    const wanted = new Set(ids);
    state.actions.queue.forEach((i) => { if (wanted.has(i.id)) i.selected = on; });
  }

  // Retargets every selected row the new repository fits, then flashes exactly the rows that changed.
  function applyBulkTarget() {
    const a = state.actions;
    const target = a.bulkTarget;
    if (!target) return;
    let changed = 0;
    let skipped = 0;
    a.queue.forEach((i) => {
      if (!i.selected) return;
      if (!canRetarget(i) || !targetsFor(i.name).includes(target)) {
        skipped += 1;
        return;
      }
      i.flash = true;
      if (i.target !== target) {
        i.target = target;
        changed += 1;
      }
    });
    a.bulkTarget = "";
    renderQueueChrome();
    renderQueueBody();
    a.queue.forEach((i) => { i.flash = false; });
    toast(t("upBulkApplied", changed, targetLabel(target)), "success", 3000);
    if (skipped) toast(t("upBulkSkipped", skipped), "info", 4000);
  }

  async function loadActionsConfig() {
    try {
      state.actions.config = await fetchJson(API.actions);
      state.actions.error = null;
    } catch (err) {
      state.actions.error = err.message;
    }
    renderActions();
  }

  // --------------------------------------------------------- visibility

  async function loadUi({ quiet = false } = {}) {
    let data;
    try {
      data = await fetchJson(API.ui);
    } catch (_) {
      if (quiet) return;
      data = {};
    }
    const visibility = data.visibility || {};
    const changed = JSON.stringify(visibility) !== JSON.stringify(state.ui);
    state.ui = visibility;
    state.announcement = data.announcement || null;
    renderAnnouncement();
    if (quiet && !changed) return;
    $$("[data-ui]").forEach((el) => { el.hidden = !shown(el.dataset.ui); });
    renderAdminLink();
    if (!viewShown(state.view)) setView("home");
    if (state.actions.tool === "docker" && !shown("docker_build")) openTool(null);
    else renderActionsPanels();
    renderAll();
    emit("ui", state.ui);
  }

  // ------------------------------------------------------------ announcement

  const readRevision = () => { try { return localStorage.getItem(ANNOUNCEMENT_KEY); } catch (_) { return null; } };

  function renderAnnouncement() {
    const el = $("#announcement");
    const a = state.announcement;
    if (!a || readRevision() === String(a.revision)) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    const iconName = { info: "message", success: "check", warning: "alert", danger: "alert" }[a.severity] || "message";
    const when = a.updated_at ? new Date(a.updated_at).toLocaleDateString(locale(), { dateStyle: "medium" }) : "";
    const label = t("annLabel")[a.severity] || t("annLabel").info;
    const signature = `${a.revision}|${state.lang}`;
    if (el.dataset.signature === signature && !el.hidden) return;
    el.dataset.signature = signature;
    el.className = `announcement sev-${a.severity}`;
    el.innerHTML = `
      <span class="announcement-icon">${icon(iconName)}</span>
      <div class="announcement-body">
        <div class="announcement-kicker"><span>${esc(label)}</span>${when ? `<time>${esc(when)}</time>` : ""}</div>
        ${a.title ? `<strong class="announcement-title">${bdi(a.title)}</strong>` : ""}
        <p class="announcement-text">${esc(a.message)}</p>
        <button class="btn btn-secondary btn-sm announcement-read" type="button" data-action="announcement-read">${icon("check")}<span>${esc(t("annDismiss"))}</span></button>
      </div>
      <button class="icon-btn announcement-close" type="button" data-action="announcement-read" title="${esc(t("annClose"))}" aria-label="${esc(t("annClose"))}">${icon("x")}</button>`;
    el.hidden = false;
  }

  function dismissAnnouncement() {
    const a = state.announcement;
    if (a) {
      try { localStorage.setItem(ANNOUNCEMENT_KEY, String(a.revision)); } catch (_) { /* storage disabled */ }
    }
    const el = $("#announcement");
    el.classList.add("leaving");
    setTimeout(() => { el.classList.remove("leaving"); renderAnnouncement(); }, 180);
  }

  function renderAdminLink() {
    const link = $("#admin-link");
    const allowed = isAdmin() && shown("btn_admin") && Boolean(state.auth.admin.path);
    link.hidden = !allowed;
    link.href = allowed ? state.auth.admin.path : "#home";
  }

  function renderChrome() {
    $("#count-apps").textContent = state.apps.length;
    const scan = state.scan;
    let html = "";
    if (scan && scan.scanning) html = `<span class="status-dot busy"></span>${esc(t("scanning"))}`;
    else if (scan && scan.last_scan) {
      const time = new Date(scan.last_scan).toLocaleString(state.lang === "he" ? "he-IL" : "en-GB", { dateStyle: "short", timeStyle: "short" });
      html = `<span class="status-dot ${scan.error ? "bad" : ""}"></span><span dir="ltr">${esc(t("syncedAt", time))}</span>`;
    }
    $("#footer-status").innerHTML = html;
    $$(".segmented [data-lang]").forEach((b) => b.classList.toggle("active", b.dataset.lang === state.lang));
  }

  function renderView() {
    VIEWS.forEach((v) => $(`#view-${v}`).classList.toggle("active", v === state.view));
    $$(".nav-item").forEach((item) => {
      const active = item.dataset.view === state.view;
      item.classList.toggle("active", active);
      if (active) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
  }

  function renderAll() {
    renderChrome();
    renderToolbar();
    renderHome();
    renderApps();
    renderBundles();
    renderPlatforms();
    renderView();
    if (state.modal) refreshModal();
  }

  // ------------------------------------------------------------------ modal

  function openModal(modal) {
    state.modal = modal;
    state.modalOs = "all";
    $("#modal-body").innerHTML = "";
    refreshModal();
    const el = $("#modal");
    el.hidden = false;
    document.body.classList.add("modal-open");
    requestAnimationFrame(() => el.classList.add("show"));
    const first = modal.type === "feedback" ? $("#feedback-form input[name='subject']")
      : modal.type === "signin" ? ($("#signin-form input[name='username']") || $("#signin-sso")) : null;
    (first || $("#modal-close")).focus();
  }

  function closeModal() {
    const el = $("#modal");
    if (el.hidden) return;
    el.classList.remove("show");
    document.body.classList.remove("modal-open");
    state.modal = null;
    if (window.location.hash.startsWith("#app/")) history.replaceState(null, "", `#${state.view}`);
    setTimeout(() => {
      el.hidden = true;
      $("#modal-body").innerHTML = "";
    }, 150);
  }

  function refreshModal() {
    if (!state.modal) return;
    // The feedback form is rendered once so catalog refreshes never wipe what the user typed.
    if (state.modal.type === "feedback") {
      if (!$("#feedback-form")) $("#modal-body").innerHTML = feedbackModal();
      return;
    }
    if (state.modal.type === "signin") {
      if (!$("#signin-box")) $("#modal-body").innerHTML = signInModal();
      return;
    }
    if (state.modal.type === "formats") {
      $("#modal-body").innerHTML = formatsModal();
      return;
    }
    const html = state.modal.type === "app" ? appModal(state.modal.id) : bundleModal(state.modal.id);
    if (html) $("#modal-body").innerHTML = html;
  }

  function appModal(id) {
    const app = state.appsById.get(id);
    if (!app) return "";
    const latestPaths = new Set(Object.values(app.latest_by_os || {}).map((f) => f.rel_path));
    const preferred = preferredFile(app);

    const primaryFiles = app.platforms.map((os) => app.latest_by_os[os]).filter(Boolean)
      .sort((a, b) => (a === preferred ? -1 : b === preferred ? 1 : 0));
    const downloadButtons = primaryFiles.map((file, i) => {
      const label = primaryFiles.length > 1 ? t("downloadFor", osLabel(file.os)) : t("downloadLatest");
      const meta = [file.version ? `v${file.version}` : "", fileSize(file)].filter(Boolean).join(" · ");
      return `<button class="btn ${i === 0 ? "btn-primary" : "btn-secondary"} btn-lg" type="button" ${downloadAttrs(file)}>${icon("download")}<span>${esc(label)}</span>${meta ? `<span class="btn-meta">${esc(meta)}</span>` : ""}</button>`;
    }).join("");

    const osFilter = app.platforms.length > 1
      ? `<div class="segmented">${["all", ...app.platforms].map((os) => `<button type="button" class="${state.modalOs === os ? "active" : ""}" data-action="modal-os" data-os="${esc(os)}">${esc(os === "all" ? t("all") : osLabel(os))}</button>`).join("")}</div>`
      : "";

    const files = app.files.filter((f) => state.modalOs === "all" || f.os === state.modalOs);
    const rows = files.map((f) => `
      <tr>
        <td>
          <div class="file-cell">
            <span class="file-name" title="${esc(f.rel_path)}">${esc(f.filename)}${latestPaths.has(f.rel_path) ? `<span class="badge">${esc(t("latest"))}</span>` : ""}</span>
            ${f.bundle_files ? `<span class="file-ctx">${esc(t("bundleCtx", f.bundle_size_human, f.bundle_files))}</span>` : ""}
          </div>
        </td>
        <td>${versionTag(f.version)}</td>
        <td><span class="os-tag">${esc(osLabel(f.os))}</span></td>
        <td class="num">${esc(f.modified)}</td>
        <td class="num">${esc(f.size_human)}</td>
        <td class="actions-cell"><button class="btn btn-secondary btn-sm" type="button" ${downloadAttrs(f)}>${icon("download")}<span>${esc(t("download"))}</span></button></td>
      </tr>`).join("");

    return `
      <div class="modal-header">
        ${appIcon(app.icon_url, app.name, "lg")}
        <div class="modal-heading">
          <h2 id="modal-title">${bdi(app.name)}</h2>
          <div class="meta"><span>${esc(categoryLabel(app.category))}</span>${(app.tags || []).length ? `<span class="tags">${app.tags.map((tag) => `<span class="tag">${bdi(tag)}</span>`).join("")}</span>` : ""}</div>
        </div>
      </div>
      <p class="modal-desc">${esc(loc(app, "description"))}</p>
      <dl class="spec-grid">
        <div><dt>${esc(t("latestVersion"))}</dt><dd>${versionTag(app.latest_version)}</dd></div>
        <div><dt>${esc(t("platformsLbl"))}</dt><dd>${osTags(app.platforms)}</dd></div>
        <div><dt>${esc(t("updated"))}</dt><dd class="mono">${esc(app.updated || "—")}</dd></div>
        <div><dt>${esc(t("totalSize"))}</dt><dd class="mono">${esc(app.total_size_human)}</dd></div>
      </dl>
      <div class="download-bar">
        ${downloadButtons}
        ${app.homepage && shown("btn_homepage") ? `<a class="btn btn-ghost btn-lg" href="${esc(app.homepage)}" target="_blank" rel="noopener noreferrer">${icon("external")}<span>${esc(t("homepage"))}</span></a>` : ""}
        ${isAdmin() && !(state.cardUpload && state.cardUpload.appId === app.id) ? `<button class="btn btn-secondary btn-lg card-upload-btn" type="button" data-action="card-upload-pick" data-id="${esc(app.id)}">${icon("upload")}<span>${esc(t("cuAdd"))}</span><span class="admin-chip">${icon("shield")}${esc(t("cuAdminOnly"))}</span></button>` : ""}
      </div>
      ${isAdmin() ? cardUploadPanel(app) : ""}
      <div class="table-head">
        <h3>${esc(t("officialInstallers"))} <span class="subtle mono">${app.files.length}</span></h3>
        ${osFilter}
      </div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr>
            <th>${esc(t("colFile"))}</th><th>${esc(t("colVersion"))}</th><th>${esc(t("colOs"))}</th>
            <th>${esc(t("colDate"))}</th><th>${esc(t("colSize"))}</th><th></th>
          </tr></thead>
          <tbody>${rows || `<tr><td colspan="6" class="muted center">${esc(t("noFilesForOs"))}</td></tr>`}</tbody>
        </table>
      </div>`;
  }

  // ------------------------------------------------ admin: add a file to an app

  const CU_BUSY = new Set(["uploading", "saving", "syncing"]);

  function cardUploadPanel(app) {
    const u = state.cardUpload;
    if (!u || u.appId !== app.id) return "";
    const busy = CU_BUSY.has(u.status);
    const pct = u.size ? Math.min(100, Math.round((100 * u.loaded) / u.size)) : 0;
    const statusLine = {
      ready: "", uploading: t("cuUploading", pct), saving: t("cuSaving"), syncing: t("cuSyncing"),
      done: t("cuLive"), hidden: t("cuSavedHidden"), error: u.error || "",
    }[u.status];
    const statusIcon = { done: "check", hidden: "alert", error: "alert" }[u.status] || (busy ? "refresh" : "");
    return `
      <section class="card-upload is-${u.status}" id="card-upload">
        <div class="card-upload-head">
          <span class="card-upload-glyph">${icon("upload")}</span>
          <div>
            <h3>${esc(t("cuAdd"))} <span class="admin-chip">${icon("shield")}${esc(t("cuAdminOnly"))}</span></h3>
            <p>${esc(t("cuIntro", app.folder || app.name))}</p>
          </div>
          <button class="icon-btn" type="button" data-action="card-upload-close" title="${esc(t("close"))}" aria-label="${esc(t("close"))}"${busy ? " disabled" : ""}>${icon("x")}</button>
        </div>
        <div class="card-upload-file">
          ${icon("file")}
          <span class="file-name">${esc(u.name)}</span>
          <span class="mono subtle" dir="ltr">${esc(humanBytes(u.size))}</span>
        </div>
        <div class="card-upload-grid">
          <label class="field">
            <span class="fb-label">${esc(t("cuFolder"))}</span>
            <input class="input mono" id="cu-folder" dir="ltr" maxlength="64" autocomplete="off" spellcheck="false" value="${esc(u.folder)}" placeholder="${esc(u.suggested || "1.2.3")}"${busy || u.status === "done" ? " disabled" : ""}>
            <span class="hint">${esc(t("cuFolderHint"))}</span>
          </label>
          ${u.exists || u.overwrite ? `<label class="check cu-overwrite"><input type="checkbox" id="cu-overwrite"${u.overwrite ? " checked" : ""}${busy ? " disabled" : ""}><span>${esc(t("cuOverwrite"))}</span></label>` : ""}
        </div>
        ${u.status === "uploading" ? `<span class="q-progress card-upload-bar" aria-hidden="true"><span id="cu-bar" style="width:${pct}%"></span></span>` : ""}
        <div class="card-upload-foot">
          <span class="card-upload-status" id="cu-status" role="status">${statusIcon ? icon(statusIcon) : ""}<span>${esc(statusLine)}</span></span>
          <span class="card-upload-actions">
            ${u.status === "uploading" ? `<button class="btn btn-ghost btn-sm" type="button" data-action="card-upload-cancel">${esc(t("upCancel"))}</button>` : ""}
            ${!busy ? `<button class="btn btn-ghost btn-sm" type="button" data-action="card-upload-pick" data-id="${esc(app.id)}">${esc(t("cuChoose"))}</button>` : ""}
            ${["ready", "error"].includes(u.status) ? `<button class="btn btn-primary btn-sm" type="button" data-action="card-upload-send">${icon("upload")}<span>${esc(t("cuUpload"))}</span></button>` : ""}
          </span>
        </div>
      </section>`;
  }

  function rerenderCardUpload() {
    const u = state.cardUpload;
    const app = u && state.appsById.get(u.appId);
    const el = $("#card-upload");
    if (state.modal && state.modal.type === "app" && app) {
      if (el) el.outerHTML = cardUploadPanel(app);
      else refreshModal();
    }
  }

  function pickCardUpload(appId) {
    if (state.cardUpload && CU_BUSY.has(state.cardUpload.status)) return;
    const input = $("#app-file-input");
    const exts = (state.auth.admin.upload_extensions || []);
    input.accept = exts.join(",");
    input.dataset.appId = appId;
    input.value = "";
    input.click();
  }

  function onCardFile(file, appId) {
    const admin = state.auth.admin;
    const exts = admin.upload_extensions || [];
    const lower = file.name.toLowerCase();
    let error = "";
    if (exts.length && !exts.some((ext) => lower.endsWith(ext))) error = t("cuBadType", exts.join(" "));
    else if (admin.upload_max_mb && file.size > admin.upload_max_mb * 1024 * 1024) error = t("cuTooLarge", admin.upload_max_mb);
    const version = (file.name.match(/\d+(?:\.\d+){1,3}/) || [""])[0];
    state.cardUpload = {
      appId, file, name: file.name, size: file.size, loaded: 0, folder: "", suggested: version,
      overwrite: false, exists: false, status: error ? "error" : "ready", error, xhr: null, relPath: "",
    };
    refreshModal();
    const folder = $("#cu-folder");
    if (folder && !error) folder.focus();
  }

  function sendCardUpload() {
    const u = state.cardUpload;
    if (!u || CU_BUSY.has(u.status)) return;
    const params = new URLSearchParams({ filename: u.name });
    if (u.folder.trim()) params.set("folder", u.folder.trim());
    if (u.overwrite) params.set("overwrite", "true");
    const xhr = new XMLHttpRequest();
    Object.assign(u, { status: "uploading", loaded: 0, error: "", xhr });
    rerenderCardUpload();
    xhr.open("PUT", `/api/manage/apps/${encodeURIComponent(u.appId)}/files?${params}`);
    xhr.setRequestHeader("X-PAKAL-Request", "1");
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable || state.cardUpload !== u) return;
      u.loaded = e.loaded;
      const pct = Math.min(100, Math.round((100 * e.loaded) / (u.size || 1)));
      const bar = $("#cu-bar");
      const label = $("#cu-status span:last-child");
      if (bar) bar.style.width = `${pct}%`;
      if (label) label.textContent = pct >= 100 ? t("cuSaving") : t("cuUploading", pct);
      if (pct >= 100 && u.status === "uploading") u.status = "saving";
    };
    const fail = (message) => {
      if (state.cardUpload !== u) return;
      Object.assign(u, { status: "error", error: message, xhr: null });
      rerenderCardUpload();
    };
    xhr.onerror = () => fail(t("upNetwork"));
    xhr.onabort = () => fail(t("upCancelled"));
    xhr.onload = () => {
      let body = null;
      try { body = JSON.parse(xhr.responseText); } catch (_) { /* non-JSON */ }
      if (state.cardUpload !== u) {
        if (xhr.status === 201) watchScan({ expectChange: true });
        return;
      }
      if (xhr.status === 201) {
        Object.assign(u, { status: "syncing", xhr: null, relPath: body.rel_path, loaded: u.size });
        rerenderCardUpload();
        watchScan({ expectChange: true });
        return;
      }
      if (xhr.status === 409) u.exists = true;
      const detail = body && body.detail;
      fail(xhr.status === 409 ? t("cuExists") : Array.isArray(detail) ? detail.map((d) => d.msg).join(" · ") : detail || `${xhr.status}`);
    };
    xhr.send(u.file);
  }

  // Called after every catalog refresh: a synced upload is "live" once its file shows up in the app.
  function settleCardUpload({ force = false } = {}) {
    const u = state.cardUpload;
    if (!u || u.status !== "syncing" || (!force && state.scan && state.scan.scanning)) return;
    const app = state.appsById.get(u.appId);
    const live = Boolean(app && app.files.some((f) => f.rel_path === u.relPath || f.filename === u.name));
    // A rescan queued behind a running one may still be on its way.
    if (!live && !force && expectChangeUntil > Date.now()) return;
    if (live) expectChangeUntil = 0;
    u.status = live ? "done" : "hidden";
    u.file = null;
    if (live) toast(t("cuDoneToast", u.name), "success", 4500);
    rerenderCardUpload();
  }

  function bundleModal(id) {
    const bundle = state.bundles.find((b) => b.id === id);
    if (!bundle) return "";
    const apps = bundle.apps.map((appId) => state.appsById.get(appId)).filter(Boolean);
    const rows = apps.map((app) => {
      const file = preferredFile(app);
      return `
        <tr>
          <td><button class="link-btn" type="button" data-action="open-app" data-id="${esc(app.id)}">${appIcon(app.icon_url, app.name, "xs")}<span>${bdi(app.name)}</span></button></td>
          <td>${versionTag((file && file.version) || app.latest_version)}</td>
          <td>${file ? `<span class="os-tag">${esc(osLabel(file.os))}</span>` : ""}</td>
          <td class="num">${esc(fileSize(file))}</td>
          <td class="actions-cell">${file ? `<button class="btn btn-secondary btn-sm" type="button" ${downloadAttrs(file)}>${icon("download")}<span>${esc(t("download"))}</span></button>` : ""}</td>
        </tr>`;
    }).join("");

    return `
      <div class="modal-header">
        ${glyphTile(bundle, "lg")}
        <div class="modal-heading">
          <span class="stack-kicker">stacks/${esc(bundle.id)}</span>
          <h2 id="modal-title">${esc(loc(bundle, "name"))}</h2>
        </div>
      </div>
      <p class="modal-desc">${esc(loc(bundle, "description"))}</p>
      <dl class="spec-grid">
        <div><dt>${esc(t("stackTools"))}</dt><dd class="mono">${apps.length}</dd></div>
        <div><dt>${esc(t("totalSize"))}</dt><dd class="mono">${esc(bundle.total_size_human)}</dd></div>
        <div><dt>${esc(t("stackOs"))}</dt><dd><span class="os-tag">${esc(userOs)}</span></dd></div>
        <div><dt>${esc(t("updated"))}</dt><dd class="mono">${esc(apps.map((a) => a.updated || "").sort().pop() || "—")}</dd></div>
      </dl>
      ${shown("btn_bundle_zip") ? `<div class="download-bar">
        <button class="btn btn-primary btn-lg" type="button" data-action="download-bundle" data-id="${esc(bundle.id)}" ${apps.length ? "" : "disabled"}>${icon("download")}<span>${esc(t("downloadAll"))}</span><span class="btn-meta">${esc(t("tools", apps.length))}</span></button>
      </div>` : ""}
      <div class="table-head"><h3>${esc(t("stackTools"))}</h3></div>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>${esc(t("navApps"))}</th><th>${esc(t("colVersion"))}</th><th>${esc(t("colOs"))}</th><th>${esc(t("colSize"))}</th><th></th></tr></thead>
          <tbody>${rows || `<tr><td colspan="5" class="muted center">${esc(t("noStackTools"))}</td></tr>`}</tbody>
        </table>
      </div>
      ${bundle.missing.length ? `<div class="notice">${icon("alert")}<span>${esc(t("missingTools", bundle.missing.length))}: <span class="mono" dir="ltr">${esc(bundle.missing.join(", "))}</span></span></div>` : ""}`;
  }

  // -------------------------------------------------------------- downloads

  function triggerDownload(url, filename) {
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
    a.download = filename || "";
    a.rel = "noopener";
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => a.remove(), 1000);
  }

  function downloadBundle(id) {
    const bundle = state.bundles.find((b) => b.id === id);
    if (!bundle) return;
    const count = bundle.apps.filter((appId) => preferredFile(state.appsById.get(appId))).length;
    if (!count) return;
    const url = `/api/bundles/${encodeURIComponent(bundle.id)}/download-zip?os=${encodeURIComponent(userOs)}`;
    triggerDownload(url, "");
    toast(t("stackDownloadStart", count, loc(bundle, "name")), "info", 6000);
  }

  // -------------------------------------------------------------- data flow

  function applyCatalog(data) {
    state.apps = data.apps || [];
    state.appsById = new Map(state.apps.map((a) => [a.id, a]));
    state.bundles = data.bundles || [];
    state.platforms = data.platforms || [];
    state.categories = data.categories || [];
    state.scan = data.scan || null;
    state.loadError = null;
    state.loading = false;
  }

  let statusTimer = null;
  let expectChangeUntil = 0;
  let idleTicks = 0;

  // Fast polling while a scan runs (or one was just requested by an upload); otherwise a cheap status check
  // keeps every open portal in sync with catalog changes made elsewhere.
  function watchScan({ expectChange = false } = {}) {
    clearTimeout(statusTimer);
    if (expectChange) expectChangeUntil = Date.now() + EXPECT_CHANGE_MS;
    const busy = Boolean(state.scan && state.scan.scanning) || expectChangeUntil > Date.now();
    statusTimer = setTimeout(async () => {
      if (expectChangeUntil && expectChangeUntil <= Date.now()) {
        expectChangeUntil = 0;
        settleCardUpload({ force: true });
      }
      if (!busy && document.hidden) {
        watchScan();
        return;
      }
      try {
        const status = await fetchJson(API.status);
        const known = state.scan && state.scan.last_scan_ts;
        if (status.scanning) {
          state.scan = { ...status, last_scan_ts: known };
          watchScan();
        } else if (status.last_scan_ts !== known || (state.scan && state.scan.scanning)) {
          await loadCatalog({ silent: true });
        } else {
          if (!busy && ++idleTicks % UI_REFRESH_TICKS === 0) loadUi({ quiet: true });
          watchScan();
        }
      } catch (_) {
        watchScan();
      }
    }, busy ? SCAN_POLL_MS : LIVE_SYNC_MS);
  }

  async function loadCatalog({ silent = false } = {}) {
    if (!silent) {
      state.loading = true;
      renderAll();
    }
    try {
      const data = await fetchJson(API.apps);
      applyCatalog(data);
      if (data.scan && data.scan.scanning && !data.apps.length) state.loading = true;
    } catch (err) {
      state.loading = false;
      state.loadError = err.message;
    }
    renderAll();
    settleCardUpload();
    watchScan();
    if (state.pendingAppId && state.appsById.has(state.pendingAppId)) {
      openModal({ type: "app", id: state.pendingAppId });
      state.pendingAppId = null;
    }
  }

  const PREFERENCE_KEYS = new Set(["pakal.theme", "pakal.lang", ANNOUNCEMENT_KEY]);

  // Drops every client-side cache (keeping theme/language preferences) and re-fetches the catalog.
  async function syncCatalog(button) {
    if (button.classList.contains("spinning")) return;
    button.classList.add("spinning");
    try {
      Object.keys(localStorage).filter((key) => !PREFERENCE_KEYS.has(key)).forEach((key) => localStorage.removeItem(key));
      sessionStorage.clear();
    } catch (_) { /* storage disabled */ }
    try {
      if (window.caches) await Promise.all((await caches.keys()).map((key) => caches.delete(key)));
    } catch (_) { /* Cache API unavailable on plain http */ }
    const started = Date.now();
    await loadCatalog({ silent: true });
    await new Promise((resolve) => setTimeout(resolve, Math.max(0, 500 - (Date.now() - started))));
    button.classList.remove("spinning");
    if (state.loadError) toast(state.loadError, "error");
    else toast(t("syncDone", state.apps.length), "success");
    if (state.modal) refreshModal();
  }

  // ------------------------------------------------------------ SSO session

  const SSO_RELOGIN_KEY = "pakal.sso.relogin";
  const SSO_TRIED_KEY = "pakal.sso.silent_tried";
  // Set by the admin console on sign-out; an explicit portal sign-in re-enables SSO entry to /admin.
  const ADMIN_NO_AUTO_KEY = "pakal.admin.no_auto_sso";
  const CSRF = { "X-PAKAL-Request": "1" };

  const tabStore = {
    get: (key) => { try { return sessionStorage.getItem(key); } catch (_) { return null; } },
    set: (key, value) => { try { sessionStorage.setItem(key, value); } catch (_) { /* storage disabled */ } },
    del: (key) => { try { sessionStorage.removeItem(key); } catch (_) { /* storage disabled */ } },
  };

  const nameInitials = (name) => String(name || "?").trim().split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  const locale = () => (state.lang === "he" ? "he-IL" : "en-GB");

  function ssoLogin(silent) {
    tabStore.set(SSO_TRIED_KEY, "1");
    if (!silent) tabStore.del(ADMIN_NO_AUTO_KEY);
    const params = new URLSearchParams({ next: window.location.pathname + window.location.search + window.location.hash });
    if (silent) params.set("silent", "1");
    window.location.assign(`/api/auth/sso/login?${params}`);
  }

  // Reads and strips the ?sso=<result> flag the callback appends (none | error | disabled).
  function takeSsoResult() {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("sso");
    if (!result) return null;
    params.delete("sso");
    params.delete("reason");
    const query = params.toString();
    history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`);
    return result;
  }

  function renderUser() {
    const slot = $("#user-slot");
    const auth = state.auth;
    if (!auth || (!auth.sso_enabled && !auth.ldap_enabled && !auth.authenticated)) {
      slot.innerHTML = "";
      return;
    }
    if (auth.authenticated) {
      const u = auth.user;
      const tip = [u.name, u.username, u.email].filter(Boolean).join(" · ");
      slot.innerHTML = `
        <span class="user-chip" title="${esc(tip)}"><span class="user-avatar">${esc(nameInitials(u.name))}</span><span class="user-name">${bdi(u.name)}</span></span>
        <button class="icon-btn bordered" type="button" data-action="logout" title="${esc(t("signOut"))}" aria-label="${esc(t("signOut"))}">${icon("logout")}</button>`;
    } else {
      slot.innerHTML = `<button class="btn btn-secondary btn-sm sign-in-btn" type="button" data-action="login">${icon("login")}<span>${esc(t("signIn"))}</span></button>`;
    }
  }

  // Everything whose visibility depends on who is signed in: user chip, admin link, admin card controls.
  function renderIdentity() {
    renderUser();
    renderAdminLink();
    if (!isAdmin() && state.cardUpload && !CU_BUSY.has(state.cardUpload.status)) state.cardUpload = null;
    if (state.modal && state.modal.type !== "signin") refreshModal();
    emit("auth", state.auth);
  }

  async function refreshAuth() {
    try {
      state.auth = await fetchJson("/api/auth/me");
    } catch (_) { /* keep what we have */ }
    renderIdentity();
  }

  function renderBanner() {
    const el = $("#sso-banner");
    const r = state.relogin;
    if (!r.mode) {
      el.hidden = true;
      el.innerHTML = "";
      return;
    }
    const countdown = r.mode === "countdown";
    const actions = countdown
      ? `<button class="btn btn-primary btn-sm" type="button" data-action="relogin-now">${icon("login")}<span>${esc(t("reloginNow"))}</span></button>
         <button class="btn btn-ghost btn-sm" type="button" data-action="relogin-cancel">${esc(t("cancel"))}</button>`
      : `<button class="btn btn-primary btn-sm" type="button" data-action="login">${icon("login")}<span>${esc(t("signIn"))}</span></button>
         <button class="btn btn-ghost btn-sm" type="button" data-action="relogin-cancel">${esc(t("dismiss"))}</button>`;
    el.innerHTML = `
      <div class="sso-banner-inner">
        <span class="sso-banner-icon">${icon(countdown ? "clock" : "user")}</span>
        <span class="sso-banner-text" id="sso-banner-text"></span>
        <span class="sso-banner-actions">${actions}</span>
      </div>
      ${countdown ? `<span class="sso-banner-progress"><span id="sso-banner-bar"></span></span>` : ""}`;
    el.hidden = false;
    tickBanner();
  }

  function tickBanner() {
    const r = state.relogin;
    const text = $("#sso-banner-text");
    if (!text) return;
    text.textContent = r.mode === "countdown" ? t("reloginCountdown", r.remaining) : t("reloginNoSession");
    const bar = $("#sso-banner-bar");
    if (bar && r.total) bar.style.width = `${(100 * r.remaining) / r.total}%`;
  }

  function stopRelogin() {
    clearInterval(state.relogin.timer);
    state.relogin = { mode: null, remaining: 0, total: 0, timer: null };
  }

  function reloginNow() {
    stopRelogin();
    if (state.auth && !state.auth.sso_reachable) {
      tabStore.del(SSO_RELOGIN_KEY);
      state.relogin.mode = "nosession";
      renderBanner();
      return;
    }
    tabStore.set(SSO_RELOGIN_KEY, "attempting");
    renderBanner();
    ssoLogin(true);
  }

  function startRelogin(cooldownMs) {
    stopRelogin();
    const total = Math.max(0, Math.ceil((Number(cooldownMs) || 0) / 1000));
    if (!total) {
      reloginNow();
      return;
    }
    const deadline = Date.now() + total * 1000;
    state.relogin = { mode: "countdown", remaining: total, total, timer: null };
    renderBanner();
    state.relogin.timer = setInterval(() => {
      const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      if (left !== state.relogin.remaining) {
        state.relogin.remaining = left;
        tickBanner();
      }
      if (left <= 0) reloginNow();
    }, 200);
  }

  function cancelRelogin() {
    tabStore.del(SSO_RELOGIN_KEY);
    tabStore.set(SSO_TRIED_KEY, "1");
    stopRelogin();
    renderBanner();
  }

  async function logout(button) {
    button.disabled = true;
    toast(t("signingOut"), "info", 2000);
    try {
      const response = await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin", headers: CSRF });
      if (!response.ok) throw new Error(`${response.status}`);
      const body = await response.json();
      state.auth = { ...state.auth, authenticated: false, user: null };
      if (!body.relogin) {
        // LDAP sessions have no identity-provider session to resume.
        tabStore.set(SSO_TRIED_KEY, "1");
        refreshAuth();
        loadActionsConfig();
        toast(t("signedOut"), "success");
        return;
      }
      tabStore.set(SSO_RELOGIN_KEY, "pending");
      if (body.logout_url) {
        window.location.assign(body.logout_url);
        return;
      }
      refreshAuth();
      startRelogin(body.sso_cooldown_ms);
    } catch (err) {
      button.disabled = false;
      toast(`${t("ssoFailed")} (${err.message})`, "error");
    }
  }

  async function initAuth() {
    const result = takeSsoResult();
    try {
      state.auth = await fetchJson("/api/auth/me");
    } catch (_) {
      state.auth = null;
    }
    renderIdentity();
    const auth = state.auth;
    const relogin = tabStore.get(SSO_RELOGIN_KEY);
    if (!auth || auth.authenticated || !auth.sso_enabled) {
      tabStore.del(SSO_RELOGIN_KEY);
      if (result === "error") toast(t("ssoFailed"), "error", 5000);
      return;
    }
    if (result === "logged_out") {
      // Back from Keycloak's end-session endpoint (KEYCLOAK_POST_LOGOUT_REDIRECT_URI).
      tabStore.set(SSO_RELOGIN_KEY, "pending");
      startRelogin(auth.sso_cooldown_ms);
      return;
    }
    if (relogin === "attempting" || (relogin && result)) {
      tabStore.del(SSO_RELOGIN_KEY);
      if (result === "error") toast(t("ssoFailed"), "error", 5000);
      else {
        state.relogin.mode = "nosession";
        renderBanner();
      }
      return;
    }
    if (relogin === "pending") {
      startRelogin(auth.sso_cooldown_ms);
      return;
    }
    if (result === "error") toast(t("ssoFailed"), "error", 5000);
    if (result) return;
    if (auth.sso_reachable && !tabStore.get(SSO_TRIED_KEY)) ssoLogin(true);
  }

  function signInModal() {
    const auth = state.auth || {};
    return `
      <div id="signin-box">
        <div class="modal-header">
          <span class="fb-head-icon">${icon("login")}</span>
          <div class="modal-heading">
            <h2 id="modal-title">${esc(t("signInTitle"))}</h2>
            <div class="meta">${esc(t("signInIntro"))}</div>
          </div>
        </div>
        <div class="signin-body">
          ${auth.ldap_enabled ? `
            <section class="signin-section" aria-labelledby="signin-ldap-title">
              <div class="signin-section-head">
                <span class="signin-section-icon">${icon("user")}</span>
                <div>
                  <h3 id="signin-ldap-title">LDAP</h3>
                  <p>${esc(t("signInLdapHint"))}</p>
                </div>
              </div>
              <form class="signin-form" id="signin-form" novalidate autocomplete="on">
                <label class="fb-field"><span class="fb-label">${esc(t("adUsername"))}</span>
                  <input class="input" name="username" dir="ltr" autocomplete="username" maxlength="128" required placeholder="${esc(t("adUsernamePh"))}"></label>
                <label class="fb-field"><span class="fb-label">${esc(t("adPassword"))}</span>
                  <input class="input" name="password" type="password" dir="ltr" autocomplete="current-password" maxlength="256" required placeholder="${esc(t("adPasswordPh"))}"></label>
                <div class="fb-error" id="signin-error" role="alert" hidden></div>
                <button class="btn btn-primary btn-lg btn-block" type="submit" id="signin-submit">${icon("login")}<span>${esc(t("adSignIn"))}</span></button>
              </form>
            </section>
            ${auth.sso_enabled ? `<div class="signin-divider"><span>${esc(t("signInOr"))}</span></div>` : ""}` : ""}
          ${auth.sso_enabled ? `
            <button class="btn btn-secondary btn-lg btn-block signin-sso" type="button" id="signin-sso" data-action="signin-sso">${icon("shield")}<span>${esc(t("signInSso"))}</span></button>` : ""}
        </div>
      </div>`;
  }

  async function submitLdapLogin(form) {
    const error = $("#signin-error");
    const button = $("#signin-submit");
    const username = form.username.value.trim();
    const password = form.password.value;
    const showError = (text) => { error.textContent = text; error.hidden = false; };
    if (!username || !password) {
      showError(t("adFailed"));
      return;
    }
    error.hidden = true;
    button.disabled = true;
    button.querySelector("span").textContent = t("adSigningIn");
    try {
      const response = await fetch("/api/auth/ldap/login", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { ...CSRF, "Content-Type": "application/json" }, body: JSON.stringify({ username, password }),
      });
      if (!response.ok) {
        form.password.value = "";
        if (response.status === 429) showError(t("adThrottled", response.headers.get("Retry-After") || 60));
        else if (response.status === 503) showError(t("adUnavailable"));
        else showError(t("adFailed"));
        return;
      }
      tabStore.del(SSO_RELOGIN_KEY);
      tabStore.del(ADMIN_NO_AUTO_KEY);
      state.auth = await fetchJson("/api/auth/me");
      const resume = state.feedbackAfterSignIn;
      state.feedbackAfterSignIn = false;
      closeModal();
      renderIdentity();
      loadActionsConfig();
      if (resume) setTimeout(openFeedback, 180);
      toast(t("signedInAs", state.auth.user ? state.auth.user.name : username), "success");
    } catch (_) {
      showError(t("adUnavailable"));
    } finally {
      button.disabled = false;
      const span = button.querySelector("span");
      if (span) span.textContent = t("adSignIn");
    }
  }

  // --------------------------------------------------------------- feedback

  const FEEDBACK_CATEGORIES = [["suggestion", "lightbulb"], ["bug", "bug"], ["app_request", "package"]];

  const lockedField = (label, value, ltr = false) => `
    <label class="fb-locked">
      <span class="fb-label">${icon("lock")}${esc(label)}</span>
      <input class="input" value="${esc(value)}" readonly aria-readonly="true" tabindex="-1"${ltr ? ' dir="ltr"' : ""}>
    </label>`;

  function feedbackGate() {
    return `
      <div class="modal-header">
        <span class="fb-head-icon">${icon("lock")}</span>
        <div class="modal-heading">
          <h2 id="modal-title">${esc(t("fbSignInTitle"))}</h2>
          <div class="meta">${esc(t("feedbackTitle"))}</div>
        </div>
      </div>
      <p class="fb-gate-text">${esc(t("fbSignInText"))}</p>
      <div class="fb-actions">
        <button class="btn btn-ghost" type="button" data-action="close-modal">${esc(t("cancel"))}</button>
        <button class="btn btn-primary btn-lg" type="button" data-action="feedback-signin">${icon("login")}<span>${esc(t("signIn"))}</span></button>
      </div>`;
  }

  function feedbackModal() {
    const auth = state.auth || {};
    const user = auth.authenticated ? auth.user : null;
    if (!user && !isAdmin()) return feedbackGate();
    const stamp = new Date().toLocaleString(locale(), { dateStyle: "short", timeStyle: "medium" });
    return `
      <div class="modal-header">
        <span class="fb-head-icon">${icon("message")}</span>
        <div class="modal-heading">
          <h2 id="modal-title">${esc(t("feedbackTitle"))}</h2>
          <div class="meta">${esc(t("feedbackIntro"))}</div>
        </div>
      </div>
      <form class="fb-form" id="feedback-form" novalidate>
        <fieldset class="fb-cats">
          <legend class="fb-label">${esc(t("fbCategory"))}</legend>
          ${FEEDBACK_CATEGORIES.map(([id, ic], i) => `
            <label class="fb-cat fb-cat-${id}">
              <input type="radio" name="category" value="${id}"${i === 0 ? " checked" : ""}>
              <span class="fb-cat-icon">${icon(ic)}</span>
              <span class="fb-cat-label">${esc(t(`fbCat_${id}`))}</span>
            </label>`).join("")}
        </fieldset>
        <label class="fb-field">
          <span class="fb-label">${esc(t("fbSubject"))}</span>
          <input class="input" name="subject" maxlength="150" required autocomplete="off" placeholder="${esc(t("fbSubjectPh"))}">
        </label>
        <label class="fb-field">
          <span class="fb-label">${esc(t("fbMessage"))}<span class="fb-counter" id="fb-counter" dir="ltr">0 / 4000</span></span>
          <textarea class="textarea" name="message" rows="5" maxlength="4000" required placeholder="${esc(t("fbMessagePh"))}"></textarea>
        </label>
        <fieldset class="fb-sender">
          <legend class="fb-label">${icon("lock")}${esc(t("fbSender"))}</legend>
          <div class="fb-locked-grid">
            ${lockedField(t("fbFullName"), user ? user.name : t("admin"))}
            ${lockedField(t("fbAccount"), user ? user.username : "—", true)}
            ${lockedField(t("fbIp"), auth.ip || "—", true)}
            ${lockedField(t("fbTime"), stamp, true)}
          </div>
        </fieldset>
        <div class="fb-error" id="fb-error" role="alert" hidden></div>
        <div class="fb-actions">
          <button class="btn btn-ghost" type="button" data-action="close-modal">${esc(t("cancel"))}</button>
          <button class="btn btn-primary btn-lg" type="submit" id="fb-submit">${icon("check")}<span>${esc(t("fbSubmit"))}</span></button>
        </div>
      </form>`;
  }

  async function openFeedback() {
    openModal({ type: "feedback" });
    if (state.auth) return;
    try {
      state.auth = await fetchJson("/api/auth/me");
      $("#modal-body").innerHTML = "";
      refreshModal();
    } catch (_) { /* identity stays "guest" */ }
  }

  async function submitFeedback(form) {
    const error = $("#fb-error");
    const button = $("#fb-submit");
    const data = new FormData(form);
    const payload = {
      category: String(data.get("category") || "suggestion"),
      subject: String(data.get("subject") || "").trim(),
      message: String(data.get("message") || "").trim(),
    };
    const showError = (text) => {
      error.textContent = text;
      error.hidden = false;
    };
    if (!payload.subject || !payload.message) {
      showError(t("fbRequired"));
      return;
    }
    error.hidden = true;
    button.disabled = true;
    button.querySelector("span").textContent = t("fbSending");
    try {
      const response = await fetch("/api/feedback", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", ...CSRF },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        if (response.status === 429) throw new Error(t("fbThrottled"));
        let detail = `${response.status}`;
        try {
          const body = await response.json();
          if (Array.isArray(body.detail)) detail = body.detail.map((d) => d.msg).join(" · ");
          else if (body.detail) detail = body.detail;
        } catch (_) { /* non-JSON body */ }
        throw new Error(detail);
      }
      closeModal();
      toast(t("fbSuccess"), "success", 4500);
    } catch (err) {
      showError(err.message);
      button.disabled = false;
      button.querySelector("span").textContent = t("fbSubmit");
    }
  }

  // ------------------------------------------------------------------- i18n

  function applyLanguage(lang) {
    state.lang = lang === "en" ? "en" : "he";
    window.PAKAL.saveLang(state.lang);
    window.PAKAL.applyDocumentLang(state.lang);
    document.title = t("docTitle");
    $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    $$("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
    $$("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); el.setAttribute("aria-label", t(el.dataset.i18nTitle)); });
    $$("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
    renderUser();
    renderBanner();
    renderAll();
    renderActions();
    renderAnnouncement();
    emit("lang", state.lang);
  }

  // ---------------------------------------------------------------- routing

  function setView(view, { updateHash = true } = {}) {
    state.view = viewShown(view) ? view : "home";
    const hash = state.view === "actions" ? actionsHash() : state.view;
    if (updateHash && window.location.hash !== `#${hash}`) history.replaceState(null, "", `#${hash}`);
    renderView();
    window.scrollTo({ top: 0 });
    if (state.view === "actions") {
      renderActionsPanels();
      if (!state.actions.running && !state.actions.aborting) loadActionsConfig();
    }
    emit("view", state.view);
    if (state.view === "actions") emit("actions-tool", state.actions.tool);
  }

  // docker.js follows the shell through these events (language, identity, visibility, current view).
  function emit(name, detail) {
    document.dispatchEvent(new CustomEvent(`pakal:${name}`, { detail }));
  }

  function setSearch(value, source) {
    state.search = value;
    if (source !== "search") $("#search").value = value;
    if (source !== "hero-search") $("#hero-search").value = value;
    syncSearchClear(value);
  }

  // Show the clear (X) button only while the search box has text.
  function syncSearchClear(value) {
    $$(".search-clear").forEach((btn) => { btn.hidden = !value; });
  }

  function focusSearch() {
    const input = state.view === "home" ? $("#hero-search") : $("#search");
    input.focus();
    input.select();
  }

  function routeFromHash() {
    const hash = decodeURIComponent(window.location.hash.slice(1));
    if (hash.startsWith("app/")) {
      const id = hash.slice(4);
      setView("apps", { updateHash: false });
      if (state.appsById.has(id)) openModal({ type: "app", id });
      else state.pendingAppId = id;
      return;
    }
    if (hash === "actions" || hash.startsWith("actions/")) {
      const tool = hash.slice("actions/".length);
      state.actions.tool = ACTION_TOOLS.includes(tool) && (tool !== "docker" || shown("docker_build")) ? tool : null;
      setView("actions", { updateHash: false });
      return;
    }
    setView(hash, { updateHash: false });
  }

  // ----------------------------------------------------------------- events

  function handleAction(el, event) {
    switch (el.dataset.action) {
      case "open-app":
        openModal({ type: "app", id: el.dataset.id });
        history.replaceState(null, "", `#app/${encodeURIComponent(el.dataset.id)}`);
        break;
      case "open-bundle":
        openModal({ type: "bundle", id: el.dataset.id });
        break;
      case "download":
        event.stopPropagation();
        triggerDownload(el.dataset.url, el.dataset.name);
        toast(t("downloadStarted", el.dataset.name), "info", 2500);
        break;
      case "download-bundle":
        event.stopPropagation();
        downloadBundle(el.dataset.id);
        break;
      case "goto":
        setView(el.dataset.view);
        break;
      case "category":
        state.category = el.dataset.category;
        renderApps();
        break;
      case "clear-search": {
        const input = el.closest(".search").querySelector("input");
        setSearch("", null);
        renderApps();
        input.focus();
        break;
      }
      case "clear-filters":
        state.category = "all";
        state.os = "all";
        setSearch("", null);
        renderToolbar();
        renderApps();
        break;
      case "modal-os":
        state.modalOs = el.dataset.os;
        refreshModal();
        break;
      case "reload":
        loadCatalog();
        break;
      case "sync":
        syncCatalog(el);
        break;
      case "feedback":
        openFeedback();
        break;
      case "close-modal":
        closeModal();
        break;
      case "login":
        tabStore.del(SSO_RELOGIN_KEY);
        if (state.auth && state.auth.ldap_enabled) {
          stopRelogin();
          renderBanner();
          openModal({ type: "signin" });
        } else ssoLogin(false);
        break;
      case "signin-sso":
        tabStore.del(SSO_RELOGIN_KEY);
        ssoLogin(false);
        break;
      case "feedback-signin":
        state.feedbackAfterSignIn = true;
        closeModal();
        setTimeout(() => handleAction({ dataset: { action: "login" } }), 160);
        break;
      case "announcement-read":
        dismissAnnouncement();
        break;
      case "card-upload-pick":
        if (isAdmin()) pickCardUpload(el.dataset.id);
        break;
      case "card-upload-send":
        sendCardUpload();
        break;
      case "card-upload-cancel":
        if (state.cardUpload && state.cardUpload.xhr) state.cardUpload.xhr.abort();
        break;
      case "card-upload-close":
        if (state.cardUpload && !CU_BUSY.has(state.cardUpload.status)) {
          state.cardUpload = null;
          refreshModal();
        }
        break;
      case "logout":
        logout(el);
        break;
      case "relogin-now":
        reloginNow();
        break;
      case "relogin-cancel":
        cancelRelogin();
        break;
      case "hub-open":
        openTool(el.dataset.tool, { push: true });
        break;
      case "hub-back":
        backToHub();
        break;
      case "pick-packages":
        if (state.actions.config && state.actions.config.configured) $("#package-input").click();
        break;
      case "pick-folder":
        if (state.actions.config && state.actions.config.configured) $("#package-folder-input").click();
        break;
      case "upload-formats":
        if (state.actions.config) openModal({ type: "formats" });
        break;
      case "upload-start":
        startUploads();
        break;
      case "upload-abort":
        abortUploads();
        break;
      case "bulk-apply":
        applyBulkTarget();
        break;
      case "queue-filter":
        state.actions.filter = el.dataset.filter;
        state.actions.visible = QUEUE_PAGE;
        renderQueue();
        break;
      case "queue-more":
        state.actions.visible += QUEUE_PAGE;
        renderQueueBody();
        break;
      case "queue-less":
        state.actions.visible = QUEUE_PAGE;
        renderQueueBody();
        $("#queue-card").scrollIntoView({ block: "start", behavior: "smooth" });
        break;
      case "queue-remove-selected":
        if (!state.actions.running) {
          state.actions.queue = state.actions.queue.filter((i) => !i.selected || i.status === "uploading");
          renderQueue();
        }
        break;
      case "upload-retry":
        retryFailed();
        break;
      case "upload-clear-done":
        state.actions.queue = state.actions.queue.filter((i) => i.status !== "success" && i.status !== "exists");
        renderQueue();
        break;
      case "upload-clear-all":
        if (!state.actions.running && !state.actions.aborting) {
          state.actions.queue = [];
          state.actions.filter = "all";
          state.actions.visible = QUEUE_PAGE;
          renderActions();
        }
        break;
      case "upload-remove":
        removeQueued(Number(el.dataset.qid));
        break;
      case "upload-cancel": {
        const item = findQueued(Number(el.dataset.qid));
        if (item && item.controller) item.controller.abort();
        break;
      }
      case "actions-reload":
        loadActionsConfig();
        break;
      default:
        break;
    }
  }

  function bindEvents() {
    document.addEventListener("click", (event) => {
      const el = event.target.closest("[data-action]");
      if (el && !el.disabled) handleAction(el, event);
    });

    document.addEventListener("keydown", (event) => {
      const target = event.target;
      const typing = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement;
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (!$("#modal").hidden) closeModal();
        focusSearch();
        return;
      }
      if (event.key === "Escape") {
        if (!$("#modal").hidden) closeModal();
        else if (typing && state.search) {
          setSearch("", null);
          renderApps();
        }
        return;
      }
      if (!typing && event.key === "/") {
        event.preventDefault();
        focusSearch();
        return;
      }
      if ((event.key === "Enter" || event.key === " ") && !typing && target.matches("[data-action][role='button']")) {
        event.preventDefault();
        handleAction(target, event);
      }
    });

    $$(".nav-item").forEach((item) => item.addEventListener("click", () => {
      if (item.dataset.view === "actions") state.actions.tool = null;
      setView(item.dataset.view);
    }));
    $$(".segmented [data-lang]").forEach((b) => b.addEventListener("click", () => applyLanguage(b.dataset.lang)));

    const onSearch = debounce((value, source) => {
      setSearch(value, source);
      if (value.trim() && state.view !== "apps") {
        setView("apps");
        const input = $("#search");
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
      }
      renderApps();
    }, 120);
    ["search", "hero-search"].forEach((id) => $(`#${id}`).addEventListener("input", (e) => {
      syncSearchClear(e.target.value);
      onSearch(e.target.value, id);
    }));

    $("#os-filter").addEventListener("change", (e) => { state.os = e.target.value; renderApps(); });
    $("#sort-select").addEventListener("change", (e) => { state.sort = e.target.value; renderApps(); });
    $("#modal-body").addEventListener("submit", (e) => {
      if (e.target.id === "signin-form") {
        e.preventDefault();
        submitLdapLogin(e.target);
        return;
      }
      if (e.target.id !== "feedback-form") return;
      e.preventDefault();
      submitFeedback(e.target);
    });
    $("#modal-body").addEventListener("input", (e) => {
      if (!e.target.closest("#feedback-form")) return;
      if (e.target.name === "message") $("#fb-counter").textContent = `${e.target.value.length} / 4000`;
      $("#fb-error").hidden = true;
    });
    $("#modal-body").addEventListener("input", (e) => {
      if (e.target.id === "cu-folder" && state.cardUpload) state.cardUpload.folder = e.target.value;
    });
    $("#modal-body").addEventListener("change", (e) => {
      if (e.target.id !== "cu-overwrite" || !state.cardUpload) return;
      state.cardUpload.overwrite = e.target.checked;
      if (state.cardUpload.exists) {
        state.cardUpload.exists = false;
        state.cardUpload.message = "";
        rerenderCardUpload();
      }
    });
    $("#app-file-input").addEventListener("change", (e) => {
      const input = e.target;
      const file = input.files && input.files[0];
      input.value = "";
      if (file) onCardFile(file, input.dataset.appId);
    });
    window.addEventListener("beforeunload", (e) => {
      if (state.cardUpload && CU_BUSY.has(state.cardUpload.status) && state.cardUpload.status !== "syncing") {
        e.preventDefault();
        e.returnValue = "";
      }
    });
    $("#modal-close").addEventListener("click", closeModal);
    $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
    window.addEventListener("hashchange", routeFromHash);
    // docker.js reports whether the Docker Image Builder card is available and its live status line.
    document.addEventListener("pakal:docker-build", (e) => {
      state.dockerBuild = e.detail;
      if (!state.actions.tool) renderHub();
    });
    bindUploaderEvents();
  }

  function bindUploaderEvents() {
    const view = $("#view-actions");
    const withFiles = (e) => Boolean(e.dataTransfer) && Array.from(e.dataTransfer.types || []).includes("Files");
    // Where a file drag would land: the Nexus tool panel, or a card on the hub. The Docker tool has its own
    // dropzone (docker.js).
    const dropTarget = (e) => {
      if (!withFiles(e) || !(e.target instanceof Element)) return null;
      const card = e.target.closest(".hub-card:not([disabled])");
      if (card && !state.actions.tool) return card.dataset.tool;
      return e.target.closest("#actions-tool-nexus") ? "nexus-tool" : null;
    };
    const highlight = (target) => {
      const zone = $("#dropzone");
      if (zone) zone.classList.toggle("dragging", target === "nexus-tool");
      $$(".hub-card").forEach((card) => card.classList.toggle("dragging", card.dataset.tool === target));
    };
    let depth = 0;
    view.addEventListener("dragenter", (e) => {
      const target = dropTarget(e);
      if (!target) return;
      e.preventDefault();
      depth += 1;
      highlight(target);
    });
    view.addEventListener("dragover", (e) => {
      const target = dropTarget(e);
      if (!target) return;
      e.preventDefault();
      const nexusReady = Boolean(state.actions.config && state.actions.config.configured);
      e.dataTransfer.dropEffect = target === "docker" || nexusReady ? "copy" : "none";
      highlight(target);
    });
    view.addEventListener("dragleave", () => {
      depth = Math.max(0, depth - 1);
      if (!depth) highlight(null);
    });
    view.addEventListener("drop", async (e) => {
      const target = dropTarget(e);
      if (!target) return;
      e.preventDefault();
      depth = 0;
      highlight(null);
      if (target === "docker") {
        const file = Array.from(e.dataTransfer.files || []).find((f) => /\.zip$/i.test(f.name)) || (e.dataTransfer.files || [])[0];
        openTool("docker", { push: true });
        if (file) emit("docker-file", file);
        return;
      }
      const dropped = await collectDropped(e.dataTransfer);
      if (target === "nexus") openTool("nexus", { push: true });
      addPackages(dropped.files, { fromFolder: dropped.fromFolder });
    });
    // A drop that misses the drop zone must not make the browser navigate away from a running batch.
    ["dragover", "drop"].forEach((type) => window.addEventListener(type, (e) => {
      if (state.view === "actions" && e.dataTransfer && Array.from(e.dataTransfer.types || []).includes("Files")) e.preventDefault();
    }));
    $("#package-input").addEventListener("change", (e) => {
      addPackages(Array.from(e.target.files || []));
      e.target.value = "";
    });
    $("#package-folder-input").addEventListener("change", (e) => {
      addPackages(Array.from(e.target.files || []), { fromFolder: true });
      e.target.value = "";
    });
    $("#actions-root").addEventListener("change", (e) => {
      const target = e.target;
      const a = state.actions;
      if (target.id === "bulk-target") {
        a.bulkTarget = target.value;
        renderQueueChrome();
      } else if (target.id === "q-select-all") {
        setSelected(filteredQueue().map((i) => i.id), target.checked);
        renderQueueChrome();
        renderQueueBody();
      } else if (target.matches("input[data-qsel]")) {
        const item = findQueued(Number(target.dataset.qsel));
        if (!item) return;
        item.selected = target.checked;
        const row = target.closest("tr");
        if (row) row.classList.toggle("is-selected", item.selected);
        renderQueueChrome();
      } else if (target.matches("select[data-qid]")) {
        const item = findQueued(Number(target.dataset.qid));
        if (item && canRetarget(item) && targetsFor(item.name).includes(target.value)) {
          item.target = target.value;
          updateRow(item);
        }
      }
    });
    window.addEventListener("beforeunload", (e) => {
      if (!state.actions.queue.some((i) => i.status === "uploading")) return;
      e.preventDefault();
      e.returnValue = t("upLeave");
    });
  }

  function init() {
    window.PAKAL.hydrateIcons();
    const shortcut = window.PAKAL.isMac ? "⌘ K" : "Ctrl K";
    $$("[data-shortcut]").forEach((el) => { el.textContent = shortcut; });
    bindEvents();
    routeFromHash();
    applyLanguage(state.lang);
    initAuth();
    loadUi().then(() => { if (state.view !== "actions") loadActionsConfig(); });
    loadCatalog();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
