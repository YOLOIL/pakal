(() => {
  "use strict";

  const { esc, icon, appIcon, toast, debounce } = window.PAKAL;
  const CSRF_HEADERS = { "X-PAKAL-Request": "1" };
  const VIEWS = ["overview", "apps", "stacks", "platforms", "feedback", "sso", "nexus", "interface"];
  const FB_STATUSES = ["new", "in_progress", "closed"];
  const FB_CATEGORIES = ["suggestion", "bug", "app_request"];
  const FB_ICONS = { suggestion: "lightbulb", bug: "bug", app_request: "package" };
  const COLORS = ["#6366F1", "#0EA5E9", "#10B981", "#8B5CF6", "#EC4899", "#F97316", "#14B8A6", "#64748B"];
  const MAX_ICON_BYTES = 512 * 1024;
  // The console is served from a single configurable segment (ADMIN_SECURE_PATH), never a fixed /admin.
  const ADMIN_BASE = "/" + (window.location.pathname.split("/")[1] || "");
  const viewPath = (view) => (view === "overview" ? ADMIN_BASE : `${ADMIN_BASE}/${view}`);

  const I18N = {
    he: {
      brand: "פ.ק.ל", adminBadge: "ניהול", openPortal: "לפורטל", logout: "התנתקות", close: "סגירה", cancel: "ביטול",
      loginTitle: "כניסה לממשק הניהול", loginSubtitle: "הגישה מוגבלת למנהלי המערכת בלבד.",
      username: "שם משתמש", password: "סיסמה", signIn: "כניסה",
      loginFailed: "שם המשתמש או הסיסמה שגויים", loginThrottled: (s) => `יותר מדי ניסיונות כושלים. נסו שוב בעוד ${s} שניות.`,
      notConfigured: "ממשק הניהול אינו מוגדר: יש להגדיר סיסמת מנהל מקומי (LOCAL_ADMIN_PASSWORD) או LDAP.",
      sessionExpired: "פג תוקף ההתחברות - יש להתחבר מחדש",
      manage: "ניהול", navOverview: "סקירת מערכת", navApps: "תוכנות", navStacks: "ערכות לפי תפקיד", navPlatforms: "פלטפורמות",
      overviewSubtitle: "מצב הסריקה, תצורת המערכת ופעולות תחזוקה.",
      forceRescan: "סריקת מאגר מחדש", refreshFavicons: "רענון אייקוני פלטפורמות",
      statScanned: "תוכנות שנסרקו", statVisible: "מוצגות בפורטל", statHidden: "מוסתרות", statInstallers: "מתקינים",
      statOverrides: "התאמות מטא-דאטה", statStacks: "ערכות", statPlatforms: "פלטפורמות",
      scanPanel: "סטטוס סריקה", scanPanelSub: "סריקת שיתוף ה-NetApp ושמירת המטמון המקומי (cache.json).",
      configPanel: "תצורה", configPanelSub: "ערכים הנטענים ממשתני הסביבה של הקונטיינר.",
      status: "מצב", idle: "ממתין", scanning: "סורק…", lastScan: "סריקה אחרונה", duration: "משך", source: "מקור נתונים",
      sourceScan: "סריקה חיה", sourceCache: "מטמון מקומי", sourceNone: "אין", shareRoot: "נתיב השיתוף",
      available: "זמין", unavailable: "לא זמין", error: "שגיאה", none: "—",
      extensions: "סיומות מתקינים", depth: "עומק סריקה", autoRescan: "סריקה אוטומטית", everyMinutes: (n) => `כל ${n} דקות`,
      schedulePanel: "תזמון סריקה אוטומטית", schedulePanelSub: "כל כמה דקות לסרוק מחדש את השיתוף. 0 מכבה סריקה אוטומטית. השינוי חל מיד.",
      rescanEvery: "סריקה כל", minutesUnit: "דקות", minutesShort: (n) => `${n} דק׳`, hoursShort: (n) => `${n} שע׳`,
      scheduleSaved: (n) => `הסריקה האוטומטית תרוץ כל ${n} דקות`, scheduleOff: "הסריקה האוטומטית כובתה",
      scheduleInvalid: "יש להזין מספר שלם בין 0 ל-10080", footerCredits: "נבנה ומתוחזק ב-❤️ על ידי צוות שרתים",
      themeToggle: "מצב תצוגה בהיר/כהה",
      disabled: "כבוי", enabled: "פעיל", iconExtraction: "חילוץ אייקונים מ-EXE", faviconFetch: "משיכת Favicon",
      rescanStarted: "סריקה מחדש החלה - המטמון נוקה", rescanRunning: "סריקה כבר מתבצעת",
      rescanDone: (a, f) => `הסריקה הושלמה: ${a} תוכנות, ${f} מתקינים`, rescanFailed: "הסריקה נכשלה",
      faviconsDone: (n, total) => `נמשכו ${n} מתוך ${total} אייקונים`,
      appsSubtitle: "עריכת שמות, תיאורים וקטגוריות, הסתרת תוכנות או קבצים פנימיים והעלאת אייקונים.",
      searchApps: "חיפוש תוכנה…", filterAll: "הכל", filterOverridden: "מותאמות", filterHidden: "מוסתרות",
      colApp: "תוכנה", colCategory: "קטגוריה", colVersion: "גרסה", colInstallers: "מתקינים", colStatus: "סטטוס",
      colUrl: "כתובת", colOrder: "סדר", colIcon: "אייקון", colDescription: "תיאור",
      badgeHidden: "מוסתרת", badgeOverridden: "מותאמת", edit: "עריכה", noApps: "לא נמצאו תוכנות בסריקה האחרונה.",
      editApp: "עריכת תוכנה", displayName: "שם תצוגה", category: "קטגוריה", auto: "אוטומטי (מהסריקה)",
      featured: "כלי מרכזי", featuredYes: "כן", featuredNo: "לא", descriptionHe: "תיאור (עברית)", descriptionEn: "תיאור (English)",
      tags: "תגיות", tagsHint: "מופרדות בפסיקים. השאירו ריק לשימוש בתגיות האוטומטיות.",
      hideApp: "הסתר תוכנה זו מהפורטל", installersVisibility: "מתקינים המוצגים בפורטל",
      installersHint: "בטלו סימון כדי להסתיר קבצים פנימיים או לא רלוונטיים.",
      icon: "אייקון", upload: "העלאת אייקון", removeUpload: "הסרת אייקון מותאם", fetchFavicon: "משיכת Favicon",
      iconSource: (s) => `מקור: ${s}`, srcUpload: "הועלה ידנית", srcExe: "חולץ מקובץ ה-EXE", srcFolder: "קובץ בתיקיית התוכנה",
      srcBuiltin: "ערכת אייקונים מובנית", srcFavicon: "Favicon מהאתר", srcNone: "ללא (ראשי תיבות)",
      iconUploaded: "האייקון עודכן", iconRemoved: "האייקון המותאם הוסר", iconTooLarge: "הקובץ גדול מ-512KB",
      faviconFetched: "ה-Favicon נמשך בהצלחה", faviconMissing: "לא נמצא Favicon בכתובת זו",
      save: "שמירה", saved: "השינויים נשמרו", resetOverrides: "איפוס התאמות", resetDone: "ההתאמות אופסו",
      confirmReset: "לאפס את כל ההתאמות של התוכנה?", confirmResetText: "השם, התיאור, הקטגוריה, האייקון והסתרות יחזרו לערכי הסריקה.",
      stacksSubtitle: "הרכבת ערכות עבודה לפי תפקיד ללא קוד - הערכות מופיעות מיידית בפורטל.",
      newStack: "ערכה חדשה", editStack: "עריכת ערכה", nameHe: "שם (עברית)", nameEn: "שם (English)",
      stackId: "מזהה", stackIdHint: "אותיות לועזיות קטנות, ספרות ומקפים. ריק = נגזר מהשם באנגלית.",
      sortOrder: "מיקום בתצוגה", sortOrderHint: "שאר הפריטים יוזזו אוטומטית - ללא כפילויות.", glyph: "סמל", color: "צבע", stackTools: (n) => `כלים בערכה (${n})`,
      availableApps: "תוכנות זמינות", selectedApps: "בערכה", searchAvailable: "סינון…",
      builderEmpty: "הוסיפו תוכנות מהרשימה", notInScan: "לא נמצא בסריקה", add: "הוספה", remove: "הסרה",
      moveUp: "העבר למעלה", moveDown: "העבר למטה", tools: (n) => (n === 1 ? "כלי אחד" : `${n} כלים`),
      missing: (n) => `${n} חסרים`, noStacks: "טרם הוגדרו ערכות.", delete: "מחיקה", deleted: "נמחק",
      confirmDeleteStack: "למחוק את הערכה?", confirmDeletePlatform: "למחוק את הפלטפורמה?",
      confirmDeleteText: "הפעולה אינה הפיכה.",
      platformsSubtitle: "קישורים למערכות הליבה ברשת הפיתוח. אייקונים נמשכים אוטומטית מה-Favicon של כל אתר.",
      newPlatform: "פלטפורמה חדשה", editPlatform: "עריכת פלטפורמה", name: "שם", url: "כתובת URL",
      builtinIcon: "אייקון מובנה (גיבוי)", uploadAfterSave: "ניתן להעלות אייקון לאחר השמירה הראשונה.",
      noPlatforms: "טרם הוגדרו פלטפורמות.", requestFailed: "הבקשה נכשלה",
      engage: "משתמשים", system: "מערכת", navFeedback: "ניהול פניות ומשובים", navSso: "הזדהות: SSO ו-LDAP",
      statFeedbackNew: "פניות חדשות",
      feedbackSubtitle: "הצעות ייעול, דיווחי תקלות ובקשות לכלים חדשים שנשלחו מהפורטל.",
      fbAll: "הכל", fbStatus_new: "חדש", fbStatus_in_progress: "בטיפול", fbStatus_closed: "סגור",
      fbCat_suggestion: "הצעת ייעול", fbCat_bug: "דיווח על תקלה", fbCat_app_request: "בקשת כלי חדש",
      fbAllCategories: "כל הקטגוריות", colDate: "תאריך ושעה", colType: "קטגוריה", colSender: "פונה", colContent: "נושא ותיאור",
      fbGuest: "אורח (לא מחובר)", fbEmpty: "אין פניות להצגה.", fbStatusSaved: (s) => `הסטטוס עודכן ל"${s}"`,
      confirmDeleteFeedback: "למחוק את הפנייה?", showMore: "הצג עוד", showLess: "הצג פחות",
      ssoSubtitle: "הגדרות ההזדהות של הפורטל: Keycloak (OpenID Connect), Active Directory / LDAP וחשבון מנהל מקומי לחירום. כל כרטיס נשמר בנפרד, וערכים שמורים גוברים על משתני הסביבה.",
      groupKeycloak: "Keycloak SSO", groupLdap: "LDAP / Active Directory", groupLocal: "חשבון מנהל מקומי (חירום)",
      card_keycloak: "Keycloak SSO (OpenID Connect)", card_keycloak_sub: "התחברות יחידה דרך Keycloak עם PKCE. נקודות הקצה נגזרות מהכתובת ומה-Realm.",
      card_ldap_server: "שרת וחיבור (Server & Bind)", card_ldap_server_sub: "כתובת בקר התחום וחשבון השירות המשמש לחיפוש משתמשים.",
      card_ldap_groups: "קבוצות ותחום (Groups & Domain)", card_ldap_groups_sub: "חברות בקבוצת המנהלים מעניקה הרשאות ניהול בפורטל.",
      card_ldap_lookup: "איתור שם תצוגה (Display-Name Lookup)", card_ldap_lookup_sub: "השלמת שם מלא ודוא\"ל מה-AD ברקע, בהגבלת זמן.",
      card_login_identity: "זהות התחברות (Login Identity)", card_login_identity_sub: "דומיין הדוא\"ל המשמש להשלמת כתובות וזהויות משתמש.",
      card_local_admin: "חשבון מנהל מקומי (Local Admin)", card_local_admin_sub: "כניסת חירום לממשק הניהול כאשר LDAP או Keycloak אינם זמינים.",
      f_keycloak_enabled: "הפעלת התחברות SSO דרך Keycloak", h_keycloak_enabled: "כאשר פעיל, הפורטל מנסה התחברות שקטה (prompt=none) ומציג כפתור \"כניסה עם Keycloak\".",
      f_keycloak_tls_insecure: "דילוג על אימות תעודת TLS (תעודה בחתימה עצמית)", h_keycloak_tls_insecure: "שווה ערך ל-rejectUnauthorized:false בבקשות ה-Token וה-Userinfo. לאימות מול CA ארגוני - כבו והגדירו KEYCLOAK_CA_BUNDLE.",
      f_keycloak_url: "כתובת Keycloak", h_keycloak_url: "כתובת הבסיס בלבד, ללא /realms/…",
      f_keycloak_realm: "Realm", h_keycloak_realm: "שם ה-Realm שבו מוגדר ה-Client.",
      f_keycloak_client_id: "Client ID", h_keycloak_client_id: "מזהה ה-Client ב-Keycloak (Standard Flow).",
      f_keycloak_client_secret: "Client Secret", h_keycloak_client_secret: "מוסתר. השאירו ריק כדי לשמור את הערך הקיים.",
      f_keycloak_redirect_uri: "Redirect URI", h_keycloak_redirect_uri: "חייב להופיע ב-Valid Redirect URIs של ה-Client, זהה תו-בתו.",
      f_keycloak_post_logout_redirect_uri: "Post-Logout Redirect URI", h_keycloak_post_logout_redirect_uri: "יעד החזרה לאחר התנתקות - יש לרשום ב-Valid Post Logout Redirect URIs.",
      f_keycloak_cooldown_after_logout_ms: "השהיה לפני התחברות מחדש", h_keycloak_cooldown_after_logout_ms: "זמן המתנה לאחר התנתקות לפני ניסיון התחברות שקטה חוזר. 0 = ללא התחברות אוטומטית.",
      f_keycloak_timeout_ms: "זמן קצוב לבקשות", h_keycloak_timeout_ms: "זמן מרבי לתשובת Keycloak בהחלפת הקוד ובשליפת פרטי המשתמש.",
      f_keycloak_admin_role: "תפקיד מנהל", h_keycloak_admin_role: "משתמש עם תפקיד זה (Realm או Client) מקבל הרשאות ניהול בפורטל.",
      f_keycloak_idp_hint: "IdP Hint", h_keycloak_idp_hint: "כינוי ספק זהות (kc_idp_hint) לדילוג על מסך הבחירה ב-Keycloak.",
      f_keycloak_prompt: "Prompt", h_keycloak_prompt: "ערך prompt לכניסה אינטראקטיבית (למשל login לאילוץ הזנת סיסמה).",
      f_keycloak_extra_scopes: "Scopes נוספים", h_keycloak_extra_scopes: "מתווספים ל-openid profile email. אם Keycloak דוחה Scope - מתבצע ניסיון חוזר עם הבסיסיים בלבד.",
      promptDefault: "(ברירת המחדל של Keycloak)", derivedEndpoints: "נקודות קצה נגזרות", requestedScopes: "Scopes מבוקשים",
      keycloakNote: "ה-Scopes הבסיסיים openid profile email נשלחים תמיד. שגיאות בהחלפת הקוד (Token) נרשמות במלואן ביומן השרת.",
      f_ldap_server_url: "כתובת שרת LDAP", h_ldap_server_url: "ldap:// או ldaps://. ניתן להזין כמה שרתים מופרדים ברווח לגיבוי.",
      f_ldap_server_search_base: "בסיס חיפוש (Search Base)", h_ldap_server_search_base: "ה-DN שממנו מתבצע חיפוש המשתמשים.",
      f_ldap_server_bind_dn: "חשבון שירות (Bind DN)", h_ldap_server_bind_dn: "חשבון לקריאה בלבד לחיפוש משתמשים וקבוצות.",
      f_ldap_server_bind_password: "סיסמת חשבון השירות", h_ldap_server_bind_password: "מוסתרת. השאירו ריק כדי לשמור את הערך הקיים.",
      f_ldap_groups_admin_group_dn: "קבוצת מנהלים (DN)", h_ldap_groups_admin_group_dn: "חברי הקבוצה (כולל קבוצות מקוננות) נכנסים לממשק הניהול עם פרטי ה-AD שלהם.",
      f_ldap_groups_netbios_domain: "דומיין NetBIOS", h_ldap_groups_netbios_domain: "לדוגמה CORP. מאפשר הזנת DOMAIN\\user ומשמש לחיבור ישיר ללא חשבון שירות.",
      f_ldap_lookup_enabled: "איתור שם תצוגה ב-AD", h_ldap_lookup_enabled: "משלים שם מלא ודוא\"ל למשתמשי SSO כאשר הטוקן חסר פרטים.",
      f_ldap_lookup_timeout_ms: "זמן קצוב לאיתור", h_ldap_lookup_timeout_ms: "זמן המתנה מרבי בזמן ההתחברות; איתור ארוך יותר ממשיך ברקע.",
      f_ldap_lookup_pause_sec: "השהיה לאחר כשל", h_ldap_lookup_pause_sec: "לאחר כשל, האיתורים מושהים למשך זמן זה כדי לא להאט התחברויות.",
      f_login_identity_email_domain: "דומיין דוא\"ל משתמשים", h_login_identity_email_domain: "משמש להשלמת דוא\"ל חסר ולחיבור user@domain כאשר אין חשבון שירות.",
      f_local_admin_username: "שם משתמש", h_local_admin_username: "שם המשתמש של חשבון החירום.",
      f_local_admin_password: "סיסמה חדשה", h_local_admin_password: "השאירו ריק כדי לשמור את הסיסמה הנוכחית. לפחות 8 תווים, נשמרת כ-bcrypt.",
      f_local_admin_password_confirm: "אימות סיסמה",
      pwFromDb: "הסיסמה הנוכחית נשמרה בממשק", pwFromEnv: "הסיסמה הנוכחית מגיעה ממשתני הסביבה",
      localAdminNote: "החשבון המקומי נבדק לפני LDAP ולכן ממשיך לעבוד גם כאשר שרתי ה-AD או Keycloak אינם זמינים.",
      pwMismatch: "הסיסמאות אינן תואמות", pwTooShort: "לפחות 8 תווים", optional: "רשות", secretNotSet: "לא הוגדר",
      secretStored: "••••••••  (נשמר - השאירו ריק כדי לא לשנות)", clearSecret: "מחיקת הערך השמור",
      msUnit: "ms", secondsUnit: "שניות", defaultValue: (v) => `ברירת מחדל: ${v}`,
      saveSection: "שמירת תת-סעיף זה", savingSection: "שומר…", sectionSaved: (time) => `נשמר בהצלחה · ${time}`,
      sectionSavedToast: (name) => `"${name}" נשמר`, fixErrors: "יש לתקן את השדות המסומנים",
      confirmSectionReset: (name) => `לשחזר את "${name}" לברירות המחדל?`,
      confirmSsoResetText: "הערכים השמורים יימחקו והמערכת תחזור לערכי משתני הסביבה.", ssoResetDone: "ההגדרות שוחזרו",
      ssoReset: "שחזור ברירות מחדל", ssoTest: "בדיקת חיבור Keycloak", ssoTesting: "בודק…",
      sourceDb: "נשמר בממשק", sourceEnv: "ברירת מחדל", sourceDbHint: "הערכים נשמרו במסד הנתונים וגוברים על משתני הסביבה.",
      sourceEnvHint: "הערכים נלקחים ממשתני הסביבה / ברירות המחדל.",
      reachable: "זמין", unreachable: "לא זמין", ssoTestOk: "כל נקודות הקצה זמינות", ssoTestFail: "חלק מנקודות הקצה אינן זמינות",
      ldapTest: "בדיקת חיבור LDAP", ldapTestOk: "החיבור ל-LDAP תקין", ldapTestFail: "החיבור ל-LDAP נכשל",
      ldapServers: "שרתים", ldapBind: "התחברות חשבון השירות", ldapBase: "בסיס החיפוש נמצא",
      lookupTest: "בדיקת איתור", lookupPlaceholder: "מזהה משתמש / שם משתמש",
      lookupFound: "המשתמש נמצא", lookupNotFound: "המשתמש לא נמצא", lookupError: "האיתור נכשל",
      displayName: "שם תצוגה", adminGroupMember: "חבר בקבוצת המנהלים", yes: "כן", no: "לא",
      testPassed: "הבדיקה עברה בהצלחה", testFailed: "הבדיקה נכשלה - הפרטים מופיעים בכרטיס", lookupPaused: (s) => `האיתור מושהה (${s} שנ')`,
      ssoStatusOn: "פעיל", ssoStatusOff: "כבוי",
      loginOr: "או", loginWithKeycloak: "כניסה עם Keycloak", loginHint: "מנהל מקומי, או חשבון AD החבר בקבוצת המנהלים.",
      ssoNoAdmin: "החשבון שלך אינו בעל הרשאת ניהול ב-PAKAL", ldapDown: "שירות הספרייה אינו זמין - היכנסו עם חשבון המנהל המקומי",
      notAdminGroup: "החשבון אינו חבר בקבוצת המנהלים של PAKAL",
      srcMsi: "חולץ מקובץ ה-MSI", msiIconExtraction: "חילוץ אייקונים מ-MSI",
      navNexus: "הגדרות Nexus", nexusSubtitle: "חיבור ה-Portal ל-Sonatype Nexus עבור מעלה החבילות בלשונית \"פעולות\". הערכים נשמרים במסד הנתונים של המערכת וחלים מיד - ללא שינוי קוד או הפעלה מחדש.",
      card_nexus: "הגדרות Nexus", card_nexus_sub: "כתובת השרת, חשבון השירות ושמות מאגרי היעד לכל סוג חבילה.",
      f_nexus_enabled: "הפעלת מעלה החבילות", h_nexus_enabled: "כאשר כבוי, לשונית \"פעולות\" מציגה הודעה והעלאות נחסמות.",
      f_nexus_tls_insecure: "דילוג על אימות תעודת TLS", h_nexus_tls_insecure: "לשרתים עם תעודה פנימית שאינה מוכרת בקונטיינר.",
      f_nexus_check_existing: "בדיקת קיום לפני העלאה", h_nexus_check_existing: "מחפש את החבילה והגרסה ב-Nexus ומסמן \"קיים\" בלי לשלוח את הקובץ.",
      f_nexus_url: "כתובת Nexus", h_nexus_url: "כתובת הבסיס, ללא /repository.",
      f_nexus_username: "חשבון שירות", h_nexus_username: "משתמש Nexus עם הרשאת nx-repository-view-*-*-add למאגרי היעד.",
      f_nexus_password: "סיסמה / Token",
      f_nexus_pypi_repo: "מאגר PyPI", h_nexus_pypi_repo: "‎.whl ו-‎.tar.gz. אפשר כמה מאגרים מופרדים בפסיקים - הראשון הוא ברירת המחדל.",
      f_nexus_npm_repo: "מאגר NPM", h_nexus_npm_repo: "‎.tgz (npm pack). אפשר כמה מאגרים מופרדים בפסיקים.",
      f_nexus_powershell_repo: "מאגר PowerShell", h_nexus_powershell_repo: "‎.nupkg - מאגר Nexus בפורמט NuGet (hosted).",
      f_nexus_max_upload_mb: "גודל קובץ מרבי", f_nexus_timeout_seconds: "זמן המתנה להעלאה",
      mbUnit: "MB", nexusNote: "ההעלאה עוברת דרך שרת ה-Portal עם חשבון השירות, ולכן המשתמשים אינם צריכים הרשאות ב-Nexus. נדרשת התחברות לפורטל.",
      nexusTest: "בדיקת החיבור (הערכים בטופס)", nexusTestOk: "Nexus זמין וכל מאגרי היעד תקינים", nexusTestFail: "בדיקת Nexus נכשלה",
      nexusReachable: "השרת זמין", nexusAuth: "גישת API", nexusRepos: "מאגרי יעד",
      repoOk: "hosted תקין", repoMissing: "לא נמצא", repoWrong: (f, ty) => `לא מתאים (${f} / ${ty})`,
      card_docker: "Docker Registry", card_docker_sub: "ה-Registry של Nexus לקטלוג ה-Docker ולבניית אימג'ים מ-ZIP בלשונית הפעולות.",
      f_docker_enabled: "הפעלת קטלוג ה-Docker", h_docker_enabled: "כאשר כבוי, לשונית Docker מציגה הודעה ובנייה נחסמת.",
      f_docker_build_enabled: "בניית אימג'ים מ-ZIP", h_docker_build_enabled: "בנייה ודחיפה דרך מנוע ה-Docker של השרת (/var/run/docker.sock).",
      f_docker_build_admin_only: "בנייה למנהלים בלבד", h_docker_build_admin_only: "מומלץ: גישה ל-Docker socket שקולה להרשאות root בשרת. כשכבוי - כל משתמש מחובר יכול לבנות.",
      f_docker_tls_insecure: "דילוג על אימות תעודת TLS", h_docker_tls_insecure: "לקריאות הקטלוג בלבד. מנוע ה-Docker צריך לסמוך על ה-Registry בעצמו (insecure-registries / תעודת CA).",
      f_docker_registry: "כתובת ה-Registry", h_docker_registry: "host:port של ה-Docker connector ב-Nexus, כפי שמופיע ב-docker pull. אפשר להקדים http:// ל-Registry ללא TLS.",
      f_docker_username: "חשבון שירות", h_docker_username: "ריק = שימוש בחשבון ה-Nexus שלמעלה. נדרשות הרשאות read ו-add/edit על מאגר ה-Docker.",
      f_docker_password: "סיסמה / Token",
      f_docker_namespace: "Namespace", h_docker_namespace: "קידומת לאימג'ים שנבנים בפורטל ומסנן לקטלוג (למשל pakal → pakal/my-app).",
      f_docker_max_context_mb: "גודל ZIP מרבי", f_docker_build_timeout_seconds: "זמן בנייה מרבי",
      dockerNote: "אימג'ים נבנים ונדחפים על ידי מנוע ה-Docker של השרת, עם חשבון השירות. אחרי הדחיפה התג המקומי נמחק כדי לא למלא את הדיסק.",
      dockerTestOk: "ה-Registry זמין והאימות הצליח", dockerTestFail: "בדיקת ה-Registry נכשלה",
      dockerRepos: "אימג'ים ב-Registry", dockerEngine: "מנוע Docker (לבנייה)",
      navInterface: "תצוגת הפורטל", interfaceSubtitle: "הצגה או הסתרה של לשוניות, כפתורים ופעולות בפורטל. השינוי חל מיד על כל המשתמשים.",
      uiGroup_tabs: "לשוניות ניווט", uiGroup_header: "סרגל עליון", uiGroup_content: "פעולות בתוכן",
      uiGroupSub_tabs: "לשונית מוסתרת נעלמת מהתפריט, והכניסה אליה בקישור ישיר מחזירה לדף הבית.",
      uiGroupSub_header: "כפתורים בסרגל העליון ובפינת המסך.",
      uiGroupSub_content: "כפתורים בכרטיסים, בחלונות הפרטים ובמעלה החבילות.",
      ui_tab_bundles: "לשונית \"ערכות לפי תפקיד\"", uid_tab_bundles: "כולל את אזור הערכות בדף הבית.",
      ui_tab_platforms: "לשונית \"פלטפורמות\"", uid_tab_platforms: "קישורי המערכות הפנימיות.",
      ui_tab_actions: "לשונית \"פעולות\"", uid_tab_actions: "מעלה החבילות ל-Nexus. כשהיא מוסתרת גם ה-API חוסם העלאות.",
      ui_tab_docker: "לשונית \"Docker\"", uid_tab_docker: "קטלוג האימג'ים מה-Registry. כשהיא מוסתרת גם ה-API של הקטלוג נחסם.",
      ui_docker_build: "בניית אימג' מ-ZIP", uid_docker_build: "הכרטיס בלשונית הפעולות. כשהוא מוסתר גם הבנייה בשרת נחסמת.",
      ui_btn_sync: "מחוון הסנכרון", uid_btn_sync: "שעת הסריקה האחרונה ורענון הקטלוג.",
      ui_btn_language: "בורר שפה", uid_btn_language: "מעבר בין עברית לאנגלית.",
      ui_btn_theme: "מצב כהה / בהיר", uid_btn_theme: "כפתור החלפת ערכת הצבעים.",
      ui_btn_admin: "קישור לממשק הניהול", uid_btn_admin: "מוצג למנהלים בלבד. הממשק עצמו זמין תמיד בכתובת הניהול המאובטחת.",
      ui_btn_feedback: "כפתור משוב", uid_btn_feedback: "הכפתור הצף לשליחת פניות. כשהוא מוסתר גם השליחה נחסמת.",
      ui_btn_quick_download: "הורדה מהירה", uid_btn_quick_download: "כפתור ההורדה בכרטיסי התוכנות וברשימות.",
      ui_btn_bundle_zip: "הורדת חבילה כ-ZIP", uid_btn_bundle_zip: "כשהוא מוסתר גם הורדת ה-ZIP בשרת נחסמת.",
      ui_btn_homepage: "קישור לאתר היצרן", uid_btn_homepage: "בחלון פרטי התוכנה.",
      ui_upload_repo_override: "בחירת מאגר ידנית", uid_upload_repo_override: "מאפשר לשנות את מאגר היעד של קובץ במעלה החבילות.",
      uiShown: "מוצג", uiHidden: "מוסתר", uiSave: "שמירת התצוגה", uiSaved: "הגדרות התצוגה נשמרו",
      uiUnsaved: "יש שינויים שלא נשמרו", uiNoChanges: "אין שינויים", uiShowAll: "הצגת הכול",
      uiResetConfirm: "להחזיר את כל רכיבי הפורטל לתצוגה?", uiResetText: "כל הלשוניות והכפתורים יוצגו שוב לכל המשתמשים.",
      uiResetDone: "כל הרכיבים מוצגים", uiHiddenCount: (n) => (n ? `${n} רכיבים מוסתרים` : "כל הרכיבים מוצגים"),
      annTitle: "הודעה צפה למשתמשים", annSubtitle: "כרטיס הודעה בפינת המסך לכל מבקרי הפורטל. כל משתמש יכול לסמן אותה כנקראה.",
      annEnabled: "הצגת ההודעה בפורטל", annEnabledHint: "כיבוי מסתיר את ההודעה מיד לכולם, בלי למחוק את התוכן.",
      annSeverity: "סוג", annSev_info: "מידע", annSev_success: "עדכון", annSev_warning: "אזהרה", annSev_danger: "דחוף",
      annTitleField: "כותרת (רשות)", annTitlePh: "לדוגמה: חלון תחזוקה", annMessage: "תוכן ההודעה",
      annMessagePh: "מה המשתמשים צריכים לדעת?", annPreview: "תצוגה מקדימה", annEmpty: "כאן יופיע תוכן ההודעה",
      annLive: (rev) => `ההודעה מוצגת (גרסה ${rev})`, annOff: "אין הודעה פעילה",
      annRepublish: "הצגה מחדש לכולם", annRepublishHint: "גם משתמשים שכבר סימנו כנקרא יראו את ההודעה שוב",
      annSave: "שמירת ההודעה", annSaved: "ההודעה נשמרה", annRepublished: "ההודעה תוצג שוב לכל המשתמשים",
      annNeedMessage: "כדי להציג את ההודעה צריך לכתוב תוכן",
    },
    en: {
      brand: "PAKAL", adminBadge: "Admin", openPortal: "Portal", logout: "Sign out", close: "Close", cancel: "Cancel",
      loginTitle: "Sign in to the admin console", loginSubtitle: "Access is restricted to system administrators.",
      username: "Username", password: "Password", signIn: "Sign in",
      loginFailed: "Invalid username or password", loginThrottled: (s) => `Too many failed attempts. Try again in ${s} seconds.`,
      notConfigured: "The admin console is not configured: set ADMIN_PASSWORD_HASH in the container environment.",
      sessionExpired: "Your session expired - please sign in again",
      manage: "Manage", navOverview: "Overview", navApps: "Applications", navStacks: "Developer Stacks", navPlatforms: "Platforms",
      overviewSubtitle: "Scan status, system configuration and maintenance actions.",
      forceRescan: "Force repository rescan", refreshFavicons: "Refresh platform icons",
      statScanned: "Scanned apps", statVisible: "Visible in portal", statHidden: "Hidden", statInstallers: "Installers",
      statOverrides: "Metadata overrides", statStacks: "Stacks", statPlatforms: "Platforms",
      scanPanel: "Scan status", scanPanelSub: "NetApp share scan and the local cache (cache.json).",
      configPanel: "Configuration", configPanelSub: "Values loaded from the container environment.",
      status: "Status", idle: "Idle", scanning: "Scanning…", lastScan: "Last scan", duration: "Duration", source: "Data source",
      sourceScan: "Live scan", sourceCache: "Local cache", sourceNone: "None", shareRoot: "Share root",
      available: "available", unavailable: "unavailable", error: "Error", none: "—",
      extensions: "Installer extensions", depth: "Scan depth", autoRescan: "Auto rescan", everyMinutes: (n) => `every ${n} minutes`,
      schedulePanel: "Automatic rescan schedule", schedulePanelSub: "How often the share is rescanned. 0 disables automatic scans. Applies immediately.",
      rescanEvery: "Rescan every", minutesUnit: "minutes", minutesShort: (n) => `${n} min`, hoursShort: (n) => `${n} h`,
      scheduleSaved: (n) => `Automatic rescan will run every ${n} minutes`, scheduleOff: "Automatic rescan disabled",
      scheduleInvalid: "Enter a whole number between 0 and 10080", footerCredits: "Built and maintained with ❤️ by the Servers Team",
      themeToggle: "Light/dark mode",
      disabled: "Disabled", enabled: "Enabled", iconExtraction: "EXE icon extraction", faviconFetch: "Favicon fetching",
      rescanStarted: "Rescan started - cache invalidated", rescanRunning: "A rescan is already running",
      rescanDone: (a, f) => `Rescan complete: ${a} apps, ${f} installers`, rescanFailed: "Rescan failed",
      faviconsDone: (n, total) => `Fetched ${n} of ${total} icons`,
      appsSubtitle: "Edit names, descriptions and categories, hide apps or internal files, and upload icons.",
      searchApps: "Search applications…", filterAll: "All", filterOverridden: "Overridden", filterHidden: "Hidden",
      colApp: "Application", colCategory: "Category", colVersion: "Version", colInstallers: "Installers", colStatus: "Status",
      colUrl: "URL", colOrder: "Order", colIcon: "Icon", colDescription: "Description",
      badgeHidden: "Hidden", badgeOverridden: "Overridden", edit: "Edit", noApps: "No applications in the latest scan.",
      editApp: "Edit application", displayName: "Display name", category: "Category", auto: "Automatic (from scan)",
      featured: "Core tool", featuredYes: "Yes", featuredNo: "No", descriptionHe: "Description (Hebrew)", descriptionEn: "Description (English)",
      tags: "Tags", tagsHint: "Comma separated. Leave empty to use the automatic tags.",
      hideApp: "Hide this application from the portal", installersVisibility: "Installers shown in the portal",
      installersHint: "Uncheck to hide internal or irrelevant files.",
      icon: "Icon", upload: "Upload icon", removeUpload: "Remove custom icon", fetchFavicon: "Fetch favicon",
      iconSource: (s) => `Source: ${s}`, srcUpload: "Uploaded", srcExe: "Extracted from the EXE", srcFolder: "File in the app folder",
      srcBuiltin: "Built-in icon set", srcFavicon: "Site favicon", srcNone: "None (initials)",
      iconUploaded: "Icon updated", iconRemoved: "Custom icon removed", iconTooLarge: "File is larger than 512KB",
      faviconFetched: "Favicon fetched", faviconMissing: "No favicon found at this URL",
      save: "Save", saved: "Changes saved", resetOverrides: "Reset overrides", resetDone: "Overrides reset",
      confirmReset: "Reset all overrides for this application?", confirmResetText: "Name, description, category, icon and hidden files revert to the scanned values.",
      stacksSubtitle: "Assemble role-based developer stacks without code - changes appear in the portal instantly.",
      newStack: "New stack", editStack: "Edit stack", nameHe: "Name (Hebrew)", nameEn: "Name (English)",
      stackId: "ID", stackIdHint: "Lowercase letters, digits and dashes. Empty = derived from the English name.",
      sortOrder: "Display position", sortOrderHint: "Other items shift automatically - no duplicates.", glyph: "Glyph", color: "Color", stackTools: (n) => `Tools in stack (${n})`,
      availableApps: "Available applications", selectedApps: "In stack", searchAvailable: "Filter…",
      builderEmpty: "Add applications from the list", notInScan: "not in scan", add: "Add", remove: "Remove",
      moveUp: "Move up", moveDown: "Move down", tools: (n) => (n === 1 ? "1 tool" : `${n} tools`),
      missing: (n) => `${n} missing`, noStacks: "No stacks defined yet.", delete: "Delete", deleted: "Deleted",
      confirmDeleteStack: "Delete this stack?", confirmDeletePlatform: "Delete this platform?",
      confirmDeleteText: "This action cannot be undone.",
      platformsSubtitle: "Links to the core systems of the development network. Icons are fetched automatically from each site's favicon.",
      newPlatform: "New platform", editPlatform: "Edit platform", name: "Name", url: "URL",
      builtinIcon: "Built-in icon (fallback)", uploadAfterSave: "You can upload an icon after the first save.",
      noPlatforms: "No platforms defined yet.", requestFailed: "Request failed",
      engage: "Users", system: "System", navFeedback: "Feedback & Requests", navSso: "Authentication: SSO & LDAP",
      statFeedbackNew: "New feedback",
      feedbackSubtitle: "Improvement suggestions, bug reports and tool requests submitted from the portal.",
      fbAll: "All", fbStatus_new: "New", fbStatus_in_progress: "In progress", fbStatus_closed: "Closed",
      fbCat_suggestion: "Suggestion", fbCat_bug: "Bug report", fbCat_app_request: "Tool request",
      fbAllCategories: "All categories", colDate: "Date & time", colType: "Category", colSender: "Sender", colContent: "Subject & details",
      fbGuest: "Guest (not signed in)", fbEmpty: "No feedback to show.", fbStatusSaved: (s) => `Status set to "${s}"`,
      confirmDeleteFeedback: "Delete this entry?", showMore: "Show more", showLess: "Show less",
      ssoSubtitle: "Portal authentication: Keycloak (OpenID Connect), Active Directory / LDAP and an emergency local admin account. Each card saves independently; saved values override the environment variables.",
      groupKeycloak: "Keycloak SSO", groupLdap: "LDAP / Active Directory", groupLocal: "Local admin account (emergency)",
      card_keycloak: "Keycloak SSO (OpenID Connect)", card_keycloak_sub: "Single sign-on through Keycloak with PKCE. Endpoints are derived from the URL and realm.",
      card_ldap_server: "Server & Bind", card_ldap_server_sub: "Domain controller address and the service account used to search for users.",
      card_ldap_groups: "Groups & Domain", card_ldap_groups_sub: "Membership in the admin group grants admin rights in the portal.",
      card_ldap_lookup: "Display-Name Lookup", card_ldap_lookup_sub: "Resolves full name and email from AD in the background, time-boxed.",
      card_login_identity: "Login Identity", card_login_identity_sub: "Email domain used to complete user addresses and identities.",
      card_local_admin: "Local Admin Account", card_local_admin_sub: "Emergency admin console sign-in when LDAP or Keycloak is unreachable.",
      f_keycloak_enabled: "Enable Keycloak SSO sign-in", h_keycloak_enabled: "When on, the portal tries a silent login (prompt=none) and shows a \"Sign in with Keycloak\" button.",
      f_keycloak_tls_insecure: "Skip TLS certificate verification (self-signed)", h_keycloak_tls_insecure: "Equivalent to rejectUnauthorized:false for the token and userinfo calls. To verify against an internal CA, turn off and set KEYCLOAK_CA_BUNDLE.",
      f_keycloak_url: "Keycloak URL", h_keycloak_url: "Base URL only, without /realms/…",
      f_keycloak_realm: "Realm", h_keycloak_realm: "Realm that contains the client.",
      f_keycloak_client_id: "Client ID", h_keycloak_client_id: "Keycloak client ID (Standard Flow).",
      f_keycloak_client_secret: "Client Secret", h_keycloak_client_secret: "Masked. Leave empty to keep the current value.",
      f_keycloak_redirect_uri: "Redirect URI", h_keycloak_redirect_uri: "Must be listed in the client's Valid Redirect URIs, byte for byte.",
      f_keycloak_post_logout_redirect_uri: "Post-Logout Redirect URI", h_keycloak_post_logout_redirect_uri: "Where Keycloak returns after sign-out - register it in Valid Post Logout Redirect URIs.",
      f_keycloak_cooldown_after_logout_ms: "Cooldown before re-login", h_keycloak_cooldown_after_logout_ms: "Wait after sign-out before a silent re-login is attempted. 0 = no automatic re-login.",
      f_keycloak_timeout_ms: "Request timeout", h_keycloak_timeout_ms: "Maximum wait for Keycloak during code exchange and userinfo.",
      f_keycloak_admin_role: "Admin role", h_keycloak_admin_role: "Users with this realm or client role get admin rights in the portal.",
      f_keycloak_idp_hint: "IdP hint", h_keycloak_idp_hint: "Identity-provider alias (kc_idp_hint) that skips Keycloak's chooser.",
      f_keycloak_prompt: "Prompt", h_keycloak_prompt: "prompt value for interactive sign-in (e.g. login forces a password prompt).",
      f_keycloak_extra_scopes: "Extra scopes", h_keycloak_extra_scopes: "Added to openid profile email. If Keycloak rejects a scope, the login is retried with the base scopes.",
      promptDefault: "(Keycloak default)", derivedEndpoints: "Derived endpoints", requestedScopes: "Requested scopes",
      keycloakNote: "The base scopes openid profile email are always requested. Token-exchange errors are logged in full on the server.",
      f_ldap_server_url: "LDAP server URL", h_ldap_server_url: "ldap:// or ldaps://. Several servers separated by spaces act as fallbacks.",
      f_ldap_server_search_base: "Search base", h_ldap_server_search_base: "DN under which users are searched.",
      f_ldap_server_bind_dn: "Service account (bind DN)", h_ldap_server_bind_dn: "Read-only account used to search users and groups.",
      f_ldap_server_bind_password: "Service account password", h_ldap_server_bind_password: "Masked. Leave empty to keep the current value.",
      f_ldap_groups_admin_group_dn: "Admin group (DN)", h_ldap_groups_admin_group_dn: "Members (including nested groups) can sign in to the admin console with their AD credentials.",
      f_ldap_groups_netbios_domain: "NetBIOS domain", h_ldap_groups_netbios_domain: "E.g. CORP. Accepts DOMAIN\\user input and is used for direct binds without a service account.",
      f_ldap_lookup_enabled: "AD display-name lookup", h_ldap_lookup_enabled: "Completes full name and email for SSO users whose token lacks them.",
      f_ldap_lookup_timeout_ms: "Lookup timeout", h_ldap_lookup_timeout_ms: "Maximum wait during sign-in; slower lookups continue in the background.",
      f_ldap_lookup_pause_sec: "Pause after failure", h_ldap_lookup_pause_sec: "After a failure, lookups pause for this long so sign-ins are not slowed down.",
      f_login_identity_email_domain: "User email domain", h_login_identity_email_domain: "Completes missing emails and is used for user@domain binds without a service account.",
      f_local_admin_username: "Username", h_local_admin_username: "Username of the emergency account.",
      f_local_admin_password: "New password", h_local_admin_password: "Leave empty to keep the current password. At least 8 characters, stored as bcrypt.",
      f_local_admin_password_confirm: "Confirm password",
      pwFromDb: "Current password was set in the console", pwFromEnv: "Current password comes from the environment",
      localAdminNote: "The local account is checked before LDAP, so it keeps working when AD or Keycloak are unreachable.",
      pwMismatch: "Passwords do not match", pwTooShort: "At least 8 characters", optional: "optional", secretNotSet: "Not set",
      secretStored: "••••••••  (stored - leave empty to keep)", clearSecret: "Delete the stored value",
      msUnit: "ms", secondsUnit: "seconds", defaultValue: (v) => `Default: ${v}`,
      saveSection: "Save this subsection", savingSection: "Saving…", sectionSaved: (time) => `Saved · ${time}`,
      sectionSavedToast: (name) => `"${name}" saved`, fixErrors: "Fix the highlighted fields",
      confirmSectionReset: (name) => `Restore "${name}" to its defaults?`,
      confirmSsoResetText: "Stored values are deleted and the environment variables apply again.", ssoResetDone: "Settings restored",
      ssoReset: "Restore defaults", ssoTest: "Test Keycloak", ssoTesting: "Testing…",
      sourceDb: "Saved in console", sourceEnv: "Defaults", sourceDbHint: "Values are stored in the database and override the environment.",
      sourceEnvHint: "Values come from the environment variables / built-in defaults.",
      reachable: "reachable", unreachable: "unreachable", ssoTestOk: "All endpoints are reachable", ssoTestFail: "Some endpoints are unreachable",
      ldapTest: "Test LDAP connection", ldapTestOk: "LDAP connection OK", ldapTestFail: "LDAP connection failed",
      ldapServers: "Servers", ldapBind: "Service account bind", ldapBase: "Search base found",
      lookupTest: "Test lookup", lookupPlaceholder: "User ID / username",
      lookupFound: "User found", lookupNotFound: "User not found", lookupError: "Lookup failed",
      displayName: "Display name", adminGroupMember: "Admin group member", yes: "Yes", no: "No",
      testPassed: "Test passed", testFailed: "Test failed - details are shown in the card", lookupPaused: (s) => `Lookup paused (${s}s)`,
      ssoStatusOn: "On", ssoStatusOff: "Off",
      loginOr: "or", loginWithKeycloak: "Sign in with Keycloak", loginHint: "Local admin, or an AD account in the admin group.",
      ssoNoAdmin: "Your account does not have the PAKAL admin role", ldapDown: "The directory service is unavailable - sign in with the local admin account",
      notAdminGroup: "Your account is not a member of the PAKAL admin group",
      srcMsi: "Extracted from the MSI", msiIconExtraction: "MSI icon extraction",
      navNexus: "Nexus Configuration", nexusSubtitle: "Connects the portal to Sonatype Nexus for the package uploader in the Actions tab. Values are stored in the portal database and apply immediately - no code change or restart.",
      card_nexus: "Nexus Configuration", card_nexus_sub: "Server address, service account and target repository names per package type.",
      f_nexus_enabled: "Enable the package uploader", h_nexus_enabled: "When off, the Actions tab shows a notice and uploads are rejected.",
      f_nexus_tls_insecure: "Skip TLS certificate verification", h_nexus_tls_insecure: "For servers with an internal certificate the container does not trust.",
      f_nexus_check_existing: "Check before uploading", h_nexus_check_existing: "Searches Nexus for the package and version and marks it \"Already exists\" without sending the file.",
      f_nexus_url: "Nexus URL", h_nexus_url: "Base address, without /repository.",
      f_nexus_username: "Service account", h_nexus_username: "Nexus user with nx-repository-view-*-*-add on the target repositories.",
      f_nexus_password: "Password / token",
      f_nexus_pypi_repo: "PyPI repository", h_nexus_pypi_repo: ".whl and .tar.gz. Several comma-separated repositories are allowed - the first is the default.",
      f_nexus_npm_repo: "NPM repository", h_nexus_npm_repo: ".tgz (npm pack). Several comma-separated repositories are allowed.",
      f_nexus_powershell_repo: "PowerShell repository", h_nexus_powershell_repo: ".nupkg - a hosted Nexus repository in NuGet format.",
      f_nexus_max_upload_mb: "Maximum file size", f_nexus_timeout_seconds: "Upload timeout",
      mbUnit: "MB", nexusNote: "Uploads go through the portal server using the service account, so users need no Nexus permissions. Portal sign-in is required.",
      nexusTest: "Test connection (form values)", nexusTestOk: "Nexus is reachable and every target repository is valid", nexusTestFail: "Nexus test failed",
      nexusReachable: "Server reachable", nexusAuth: "API access", nexusRepos: "Target repositories",
      repoOk: "hosted, OK", repoMissing: "not found", repoWrong: (f, ty) => `wrong type (${f} / ${ty})`,
      card_docker: "Docker Registry", card_docker_sub: "The Nexus registry behind the Docker catalog and the ZIP-to-image builds on the Actions tab.",
      f_docker_enabled: "Enable the Docker catalog", h_docker_enabled: "When off, the Docker tab shows a notice and builds are rejected.",
      f_docker_build_enabled: "Build images from ZIP", h_docker_build_enabled: "Builds and pushes through the server's Docker engine (/var/run/docker.sock).",
      f_docker_build_admin_only: "Admins only", h_docker_build_admin_only: "Recommended: Docker socket access is equivalent to root on the host. When off, any signed-in user can build.",
      f_docker_tls_insecure: "Skip TLS certificate verification", h_docker_tls_insecure: "For catalog reads only. The Docker engine must trust the registry itself (insecure-registries / CA certificate).",
      f_docker_registry: "Registry address", h_docker_registry: "host:port of the Nexus Docker connector, as used in docker pull. Prefix http:// for a registry without TLS.",
      f_docker_username: "Service account", h_docker_username: "Empty = use the Nexus account above. Needs read and add/edit on the Docker repository.",
      f_docker_password: "Password / token",
      f_docker_namespace: "Namespace", h_docker_namespace: "Prefix for images built in the portal and a filter for the catalog (e.g. pakal → pakal/my-app).",
      f_docker_max_context_mb: "Maximum ZIP size", f_docker_build_timeout_seconds: "Build timeout",
      dockerNote: "Images are built and pushed by the server's Docker engine with the service account. After the push the local tag is removed so the disk doesn't fill up.",
      dockerTestOk: "The registry is reachable and authentication succeeded", dockerTestFail: "Registry test failed",
      dockerRepos: "Images in the registry", dockerEngine: "Docker engine (for builds)",
      navInterface: "Portal interface", interfaceSubtitle: "Show or hide tabs, buttons and actions in the portal. Changes apply immediately to every user.",
      uiGroup_tabs: "Navigation tabs", uiGroup_header: "Header", uiGroup_content: "Content actions",
      uiGroupSub_tabs: "A hidden tab disappears from the menu, and direct links to it fall back to the home page.",
      uiGroupSub_header: "Buttons in the top bar and the screen corner.",
      uiGroupSub_content: "Buttons on cards, in detail dialogs and in the package uploader.",
      ui_tab_bundles: "\"Developer Stacks\" tab", uid_tab_bundles: "Includes the stacks section on the home page.",
      ui_tab_platforms: "\"Platforms\" tab", uid_tab_platforms: "Links to the internal platforms.",
      ui_tab_actions: "\"Actions\" tab", uid_tab_actions: "The Nexus package uploader. When hidden, the API rejects uploads too.",
      ui_tab_docker: "\"Docker\" tab", uid_tab_docker: "The registry image catalog. When hidden, the catalog API is blocked too.",
      ui_docker_build: "ZIP to Docker image", uid_docker_build: "The card on the Actions tab. When hidden, server-side builds are blocked too.",
      ui_btn_sync: "Sync indicator", uid_btn_sync: "Last scan time and catalog refresh.",
      ui_btn_language: "Language switch", uid_btn_language: "Toggles Hebrew and English.",
      ui_btn_theme: "Dark / light mode", uid_btn_theme: "The theme toggle button.",
      ui_btn_admin: "Admin console link", uid_btn_admin: "Shown to admins only. The console itself always stays reachable at its secure URL.",
      ui_btn_feedback: "Feedback button", uid_btn_feedback: "The floating feedback button. When hidden, submissions are rejected too.",
      ui_btn_quick_download: "Quick download", uid_btn_quick_download: "The download button on app cards and lists.",
      ui_btn_bundle_zip: "Bundle ZIP download", uid_btn_bundle_zip: "When hidden, the server rejects ZIP downloads too.",
      ui_btn_homepage: "Vendor homepage link", uid_btn_homepage: "In the app details dialog.",
      ui_upload_repo_override: "Manual repository choice", uid_upload_repo_override: "Lets users change a file's target repository in the uploader.",
      uiShown: "Shown", uiHidden: "Hidden", uiSave: "Save interface", uiSaved: "Interface settings saved",
      uiUnsaved: "Unsaved changes", uiNoChanges: "No changes", uiShowAll: "Show everything",
      uiResetConfirm: "Show every portal element again?", uiResetText: "All tabs and buttons become visible to every user.",
      uiResetDone: "Every element is shown", uiHiddenCount: (n) => (n ? `${n} hidden element${n === 1 ? "" : "s"}` : "Everything is shown"),
      annTitle: "Floating announcement", annSubtitle: "A card in the corner of the portal for every visitor. Each user can mark it as read.",
      annEnabled: "Show the announcement", annEnabledHint: "Turning it off hides it for everyone immediately and keeps the text.",
      annSeverity: "Type", annSev_info: "Info", annSev_success: "Update", annSev_warning: "Warning", annSev_danger: "Urgent",
      annTitleField: "Title (optional)", annTitlePh: "e.g. Maintenance window", annMessage: "Message",
      annMessagePh: "What should users know?", annPreview: "Preview", annEmpty: "Your message appears here",
      annLive: (rev) => `Announcement is live (revision ${rev})`, annOff: "No active announcement",
      annRepublish: "Show again to everyone", annRepublishHint: "Users who already marked it as read will see it again",
      annSave: "Save announcement", annSaved: "Announcement saved", annRepublished: "Announcement will be shown to everyone again",
      annNeedMessage: "Write a message before turning the announcement on",
    },
  };

  const state = {
    lang: window.PAKAL.loadLang(),
    view: "overview",
    session: null,
    overview: null,
    apps: [],
    stacks: [],
    platforms: [],
    options: { builtin_icons: [], stack_glyphs: [], categories: [] },
    appSearch: "",
    appFilter: "all",
    drawer: null,
    builder: null,
    builderSearch: "",
    uploadTarget: null,
    scanning: false,
    feedback: { items: [], counts: { new: 0, in_progress: 0, closed: 0 } },
    fbStatus: "all",
    fbCategory: "all",
    fbExpanded: new Set(),
    auth: null,
    authTests: {},
    authStatus: {},
    ui: null,
    uiDraft: null,
  };

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  function t(key, ...args) {
    const value = (I18N[state.lang] && I18N[state.lang][key]) ?? I18N.he[key] ?? key;
    return typeof value === "function" ? value(...args) : value;
  }
  const loc = (obj, field) => obj[`${field}_${state.lang}`] || obj[`${field}_he`] || obj[`${field}_en`] || "";
  const normalize = (v) => String(v || "").toLowerCase().replace(/\+/g, "p").replace(/[^a-z0-9\u0590-\u05ff]/g, "");
  const bdi = (text) => `<bdi>${esc(text)}</bdi>`;

  function categoryLabel(id) {
    const c = state.options.categories.find((x) => x.id === id);
    return c ? (state.lang === "en" ? c.label_en : c.label_he) : id;
  }

  // -------------------------------------------------------------------- api

  class ApiError extends Error {
    constructor(message, status, retryAfter) {
      super(message);
      this.status = status;
      this.retryAfter = retryAfter;
    }
  }

  function errorDetail(body, fallback) {
    if (!body || body.detail === undefined) return fallback;
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join(" · ");
    }
    return fallback;
  }

  async function api(method, url, body) {
    const init = { method, credentials: "same-origin", cache: "no-store", headers: { ...CSRF_HEADERS } };
    if (body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }
    const res = await fetch(url, init);
    if (res.status === 401 && url !== "/api/admin/login") {
      showLogin(t("sessionExpired"));
      throw new ApiError(t("sessionExpired"), 401);
    }
    if (!res.ok) {
      let parsed = null;
      try { parsed = await res.json(); } catch (_) { /* no body */ }
      throw new ApiError(errorDetail(parsed, `${t("requestFailed")} (${res.status})`), res.status, res.headers.get("Retry-After"));
    }
    return res.status === 204 ? null : res.json();
  }

  const fail = (err) => { if (err.status !== 401) toast(err.message || t("requestFailed"), "error", 5000); };

  // ------------------------------------------------------------------ auth

  let expiryTimer = null;

  function showLogin(message = "") {
    state.session = null;
    clearTimeout(expiryTimer);
    closeDrawer();
    $("#shell").hidden = true;
    $("#login-view").hidden = false;
    $("#user-chip").hidden = true;
    $("#logout-btn").hidden = true;
    $("#header-rescan").hidden = true;
    $("#login-error").textContent = message;
    setTimeout(() => $("#login-form [name=username]").focus(), 0);
  }

  async function showShell(session) {
    state.session = session;
    $("#login-view").hidden = true;
    $("#shell").hidden = false;
    $("#user-chip").hidden = false;
    $("#logout-btn").hidden = false;
    $("#header-rescan").hidden = false;
    $("#user-name").textContent = session.name && session.name !== session.username ? `${session.name} (${session.username})` : session.username;
    $("#user-chip").title = { local: "Local admin", ldap: "LDAP / Active Directory", sso: "Keycloak SSO" }[session.source] || "";
    clearTimeout(expiryTimer);
    const ms = session.expires_at * 1000 - Date.now();
    if (ms > 0) expiryTimer = setTimeout(() => showLogin(t("sessionExpired")), Math.min(ms, 2 ** 31 - 1));
    await loadAll();
  }

  async function onLogin(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $("button[type=submit]", form);
    $("#login-error").textContent = "";
    button.disabled = true;
    try {
      const session = await api("POST", "/api/admin/login", {
        username: form.username.value.trim(),
        password: form.password.value,
      });
      form.password.value = "";
      await showShell(session);
    } catch (err) {
      if (err.status === 429) $("#login-error").textContent = t("loginThrottled", err.retryAfter || 60);
      else if (err.status === 503) $("#login-error").textContent = /directory/i.test(err.message) ? t("ldapDown") : t("notConfigured");
      else if (err.status === 401) $("#login-error").textContent = t("loginFailed");
      else if (err.status === 403) $("#login-error").textContent = t("notAdminGroup");
      else $("#login-error").textContent = err.message;
    } finally {
      button.disabled = false;
    }
  }

  const NO_AUTO_SSO = "pakal.admin.no_auto_sso";

  async function trySsoSession() {
    const res = await fetch("/api/admin/sso-session", { method: "POST", credentials: "same-origin", cache: "no-store", headers: CSRF_HEADERS });
    if (res.ok) return res.json();
    if (res.status === 403) $("#login-error").textContent = t("ssoNoAdmin");
    return null;
  }

  async function logout() {
    $("#logout-btn").disabled = true;
    clearTimeout(expiryTimer);
    try { sessionStorage.setItem(NO_AUTO_SSO, "1"); } catch (_) { /* storage disabled */ }
    try { await api("POST", "/api/admin/logout"); } catch (_) { /* already signed out */ }
    state.session = null;
    window.location.replace("/");
  }

  // -------------------------------------------------------------- loading

  async function loadAll() {
    try {
      const [options, overview, apps, stacks, platforms, feedback, auth, ui, announcement] = await Promise.all([
        api("GET", "/api/admin/options"), api("GET", "/api/admin/overview"), api("GET", "/api/admin/apps"),
        api("GET", "/api/admin/stacks"), api("GET", "/api/admin/platforms"), api("GET", "/api/admin/feedback"),
        api("GET", "/api/admin/auth"), api("GET", "/api/admin/ui"), api("GET", "/api/admin/announcement"),
      ]);
      Object.assign(state, {
        options, overview, apps, stacks, platforms, feedback, auth, ui, uiDraft: { ...ui.visibility },
        announcement, annDraft: { ...announcement },
      });
      state.scanning = Boolean(overview.scan.scanning);
      render();
      if (state.scanning) pollScan();
    } catch (err) {
      fail(err);
    }
  }

  async function reload(...keys) {
    const urls = {
      overview: "/api/admin/overview", apps: "/api/admin/apps", stacks: "/api/admin/stacks", platforms: "/api/admin/platforms",
      feedback: "/api/admin/feedback", auth: "/api/admin/auth",
    };
    const results = await Promise.all(keys.map((k) => api("GET", urls[k])));
    keys.forEach((k, i) => { state[k] = results[i]; });
    render();
  }

  // ------------------------------------------------------------ rendering

  function render() {
    $$(".side-item").forEach((b) => b.classList.toggle("active", b.dataset.view === state.view));
    $("#count-apps").textContent = state.apps.length || "";
    $("#count-stacks").textContent = state.stacks.length || "";
    $("#count-platforms").textContent = state.platforms.length || "";
    const newFeedback = state.feedback.counts.new || 0;
    $("#count-feedback").hidden = !newFeedback;
    $("#count-feedback").textContent = newFeedback;
    updateSsoDot();
    updateNexusDot();
    updateHiddenCount();
    const headerRescan = $("#header-rescan");
    headerRescan.disabled = state.scanning;
    headerRescan.classList.toggle("is-busy", state.scanning);
    headerRescan.innerHTML = `${icon("refresh")}<span>${esc(state.scanning ? t("scanning") : t("forceRescan"))}</span>`;
    const main = $("#admin-main");
    const renderers = {
      overview: renderOverview, apps: renderApps, stacks: renderStacks, platforms: renderPlatforms,
      feedback: renderFeedback, sso: renderSso, nexus: renderNexus, interface: renderInterface,
    };
    main.innerHTML = (renderers[state.view] || renderOverview)();
    if (state.view === "apps") {
      const input = $("#app-search");
      if (input && document.activeElement !== input && state.appSearch) input.value = state.appSearch;
    }
  }

  function pageHead(title, subtitle, actions = "") {
    return `<div class="page-head"><div><h1 class="page-title">${esc(title)}</h1><p class="page-subtitle">${esc(subtitle)}</p></div><div class="toolbar">${actions}</div></div>`;
  }

  function renderOverview() {
    const o = state.overview;
    if (!o) return "";
    const s = o.scan;
    const c = o.counts;
    const stat = (label, value) => `<div class="card stat"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`;
    const sourceLabel = { scan: t("sourceScan"), cache: t("sourceCache"), none: t("sourceNone") }[s.source] || s.source;
    const lastScan = s.last_scan ? new Date(s.last_scan).toLocaleString(state.lang === "he" ? "he-IL" : "en-GB") : t("none");
    const actions = `
      <button class="btn btn-secondary" type="button" data-action="refresh-favicons">${icon("globe")}<span>${esc(t("refreshFavicons"))}</span></button>
      <button class="btn btn-primary ${state.scanning ? "is-busy" : ""}" type="button" data-action="rescan" ${state.scanning ? "disabled" : ""}>${icon("refresh")}<span>${esc(state.scanning ? t("scanning") : t("forceRescan"))}</span></button>`;
    return `
      ${pageHead(t("navOverview"), t("overviewSubtitle"), actions)}
      <dl class="stats">
        ${stat(t("statScanned"), c.scanned_apps)}${stat(t("statVisible"), c.visible_apps)}${stat(t("statHidden"), c.hidden_apps)}
        ${stat(t("statInstallers"), c.installers)}${stat(t("statStacks"), c.stacks)}${stat(t("statPlatforms"), c.platforms)}
        ${stat(t("statFeedbackNew"), c.feedback_new ?? 0)}
      </dl>
      <section class="card panel" style="margin-top:16px">
        <div class="panel-head"><div><h3>${esc(t("scanPanel"))}</h3><p>${esc(t("scanPanelSub"))}</p></div></div>
        <dl class="kv">
          <dt>${esc(t("status"))}</dt><dd><span class="status-dot ${state.scanning ? "busy" : s.error ? "bad" : ""}"></span>${esc(state.scanning ? t("scanning") : t("idle"))}</dd>
          <dt>${esc(t("lastScan"))}</dt><dd class="mono" dir="ltr" style="text-align:start">${esc(lastScan)}</dd>
          <dt>${esc(t("duration"))}</dt><dd class="mono">${s.duration_ms != null ? `${(s.duration_ms / 1000).toFixed(2)}s` : t("none")}</dd>
          <dt>${esc(t("source"))}</dt><dd>${esc(sourceLabel)}</dd>
          <dt>${esc(t("shareRoot"))}</dt><dd><span class="mono" dir="ltr">${esc(o.config.apps_root)}</span> <span class="badge ${s.root_available ? "" : "badge-danger"}">${esc(s.root_available ? t("available") : t("unavailable"))}</span></dd>
          ${s.error ? `<dt>${esc(t("error"))}</dt><dd class="mono" style="color:var(--danger)">${esc(s.error)}</dd>` : ""}
        </dl>
      </section>
      <section class="card panel">
        <div class="panel-head"><div><h3>${esc(t("schedulePanel"))}</h3><p>${esc(t("schedulePanelSub"))}</p></div></div>
        <div class="schedule-row">
          <label class="field schedule-field"><span>${esc(t("rescanEvery"))}</span>
            <span class="input-suffix" dir="ltr"><input class="input mono" id="rescan-minutes" type="number" min="0" max="10080" step="1" inputmode="numeric" value="${esc(o.config.auto_rescan_minutes)}"><span class="suffix">${esc(t("minutesUnit"))}</span></span>
          </label>
          <div class="schedule-presets">
            ${[15, 30, 60, 240, 1440, 0].map((m) => `<button class="btn btn-secondary btn-sm" type="button" data-action="schedule-preset" data-minutes="${m}">${esc(m === 0 ? t("disabled") : m >= 60 ? t("hoursShort", m / 60) : t("minutesShort", m))}</button>`).join("")}
          </div>
          <button class="btn btn-primary" type="button" data-action="save-schedule">${icon("check")}<span>${esc(t("save"))}</span></button>
        </div>
      </section>
      <section class="card panel">
        <div class="panel-head"><div><h3>${esc(t("configPanel"))}</h3><p>${esc(t("configPanelSub"))}</p></div></div>
        <dl class="kv">
          <dt>${esc(t("extensions"))}</dt><dd class="mono" dir="ltr" style="text-align:start">${esc(o.config.installer_extensions.join("  "))}</dd>
          <dt>${esc(t("depth"))}</dt><dd class="mono">${esc(o.config.max_scan_depth)}</dd>
          <dt>${esc(t("autoRescan"))}</dt><dd>${esc(o.config.auto_rescan_minutes > 0 ? t("everyMinutes", o.config.auto_rescan_minutes) : t("disabled"))}</dd>
          <dt>${esc(t("iconExtraction"))}</dt><dd>${esc(o.config.icon_extraction ? t("enabled") : t("disabled"))}</dd>
          <dt>${esc(t("msiIconExtraction"))}</dt><dd>${esc(o.config.msi_icon_extraction ? t("enabled") : t("disabled"))}</dd>
          <dt>${esc(t("faviconFetch"))}</dt><dd>${esc(o.config.favicon_fetch ? t("enabled") : t("disabled"))}</dd>
          <dt>${esc(t("statOverrides"))}</dt><dd class="mono">${esc(c.overrides)}</dd>
        </dl>
      </section>`;
  }

  function filteredApps() {
    const terms = state.appSearch.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return state.apps.filter((a) => {
      if (state.appFilter === "hidden" && !a.hidden) return false;
      if (state.appFilter === "overridden" && !a.override) return false;
      if (!terms.length) return true;
      const hay = `${a.name} ${a.scanned_name} ${a.folder} ${a.id}`.toLowerCase();
      return terms.every((term) => hay.includes(term));
    });
  }

  function appRows() {
    const list = filteredApps();
    if (!list.length) return `<tr><td colspan="6" class="muted center">${esc(t("noApps"))}</td></tr>`;
    return list.map((a) => {
      const visibleFiles = a.files.filter((f) => !f.hidden).length;
      return `
        <tr class="clickable ${a.hidden ? "is-hidden" : ""}" data-action="edit-app" data-id="${esc(a.id)}">
          <td><div class="row-main">${appIcon(a.icon_url, a.name, "sm")}<div style="min-width:0"><div class="row-title">${bdi(a.name)}</div><div class="row-sub">${esc(a.folder)}</div></div></div></td>
          <td class="muted">${esc(categoryLabel(a.category))}</td>
          <td>${a.latest_version ? `<span class="version-tag">v${esc(a.latest_version)}</span>` : "—"}</td>
          <td class="num">${visibleFiles}/${a.files.length}</td>
          <td>${a.hidden ? `<span class="badge badge-danger">${esc(t("badgeHidden"))}</span>` : ""}${a.override ? `<span class="badge badge-accent">${esc(t("badgeOverridden"))}</span>` : ""}</td>
          <td class="actions-cell"><button class="btn btn-ghost btn-sm" type="button" data-action="edit-app" data-id="${esc(a.id)}">${icon("edit")}<span>${esc(t("edit"))}</span></button></td>
        </tr>`;
    }).join("");
  }

  function renderApps() {
    const filters = ["all", "overridden", "hidden"].map((f) => `<button type="button" class="${state.appFilter === f ? "active" : ""}" data-action="app-filter" data-filter="${f}">${esc(t(`filter${f[0].toUpperCase()}${f.slice(1)}`))}</button>`).join("");
    return `
      ${pageHead(t("navApps"), t("appsSubtitle"), `
        <label class="search">${icon("search")}<input id="app-search" type="search" autocomplete="off" placeholder="${esc(t("searchApps"))}" value="${esc(state.appSearch)}"></label>
        <div class="segmented">${filters}</div>`)}
      <div class="table-wrap card">
        <table class="table">
          <thead><tr><th>${esc(t("colApp"))}</th><th>${esc(t("colCategory"))}</th><th>${esc(t("colVersion"))}</th><th>${esc(t("colInstallers"))}</th><th>${esc(t("colStatus"))}</th><th></th></tr></thead>
          <tbody id="apps-tbody">${appRows()}</tbody>
        </table>
      </div>`;
  }

  function resolveRef(ref) {
    const key = normalize(ref);
    return state.apps.find((a) => a.id === ref || normalize(a.folder) === key || normalize(a.scanned_name) === key || a.known_key === ref) || null;
  }

  function renderStacks() {
    const cards = state.stacks.map((s) => {
      const resolved = s.apps.map(resolveRef);
      const missing = resolved.filter((a) => !a).length;
      return `
        <article class="card stack-card">
          <header class="stack-head">
            <span class="glyph-tile" style="--tint:${esc(s.color)}">${icon(s.icon)}</span>
            <div style="min-width:0;flex:1">
              <span class="stack-kicker">stacks/${esc(s.id)}</span>
              <h3>${esc(loc(s, "name"))}</h3>
              <p>${esc(loc(s, "description"))}</p>
            </div>
          </header>
          <div class="tags">${resolved.filter(Boolean).slice(0, 10).map((a) => `<span class="tag">${bdi(a.name)}</span>`).join("")}</div>
          <footer class="stack-foot">
            <span class="stack-meta">${esc(t("tools", s.apps.length - missing))}${missing ? ` · <span class="warn">${esc(t("missing", missing))}</span>` : ""} · #${esc(s.sort_order)}</span>
            <span class="stack-actions">
              <button class="btn btn-ghost btn-sm" type="button" data-action="delete-stack" data-id="${esc(s.id)}">${icon("trash")}<span>${esc(t("delete"))}</span></button>
              <button class="btn btn-secondary btn-sm" type="button" data-action="edit-stack" data-id="${esc(s.id)}">${icon("edit")}<span>${esc(t("edit"))}</span></button>
            </span>
          </footer>
        </article>`;
    }).join("");
    return `
      ${pageHead(t("navStacks"), t("stacksSubtitle"), `<button class="btn btn-primary" type="button" data-action="new-stack">${icon("plus")}<span>${esc(t("newStack"))}</span></button>`)}
      <div class="grid grid-stacks">${cards || `<div class="empty"><span class="empty-icon">${icon("layers")}</span><p>${esc(t("noStacks"))}</p></div>`}</div>`;
  }

  function platformSource(p) {
    if (p.icon_file) return t("srcUpload");
    if (p.favicon_file) return t("srcFavicon");
    if (p.icon_url) return t("srcBuiltin");
    return t("srcNone");
  }

  function renderPlatforms() {
    const rows = state.platforms.map((p) => `
      <tr class="clickable" data-action="edit-platform" data-id="${p.id}">
        <td><div class="row-main">${appIcon(p.icon_url, p.name, "sm")}<div style="min-width:0"><div class="row-title">${esc(p.name)}</div><div class="row-sub">${esc(p.url)}</div></div></div></td>
        <td class="muted">${esc(loc(p, "description"))}</td>
        <td class="subtle">${esc(platformSource(p))}</td>
        <td class="num">${esc(p.sort_order)}</td>
        <td class="actions-cell"><span class="cell-actions">
          <button class="icon-btn icon-btn-sm" type="button" data-action="delete-platform" data-id="${p.id}" title="${esc(t("delete"))}" aria-label="${esc(t("delete"))}">${icon("trash")}</button>
          <button class="btn btn-ghost btn-sm" type="button" data-action="edit-platform" data-id="${p.id}">${icon("edit")}<span>${esc(t("edit"))}</span></button>
        </span></td>
      </tr>`).join("");
    return `
      ${pageHead(t("navPlatforms"), t("platformsSubtitle"), `<button class="btn btn-primary" type="button" data-action="new-platform">${icon("plus")}<span>${esc(t("newPlatform"))}</span></button>`)}
      <div class="table-wrap card">
        <table class="table">
          <thead><tr><th>${esc(t("name"))}</th><th>${esc(t("colDescription"))}</th><th>${esc(t("colIcon"))}</th><th>${esc(t("colOrder"))}</th><th></th></tr></thead>
          <tbody>${rows || `<tr><td colspan="5" class="muted center">${esc(t("noPlatforms"))}</td></tr>`}</tbody>
        </table>
      </div>`;
  }

  // -------------------------------------------------------------- feedback

  const fmtDateTime = (iso) => (iso
    ? new Date(iso).toLocaleString(state.lang === "he" ? "he-IL" : "en-GB", { dateStyle: "short", timeStyle: "short" })
    : "—");

  function filteredFeedback() {
    return state.feedback.items.filter((f) => (state.fbStatus === "all" || f.status === state.fbStatus)
      && (state.fbCategory === "all" || f.category === state.fbCategory));
  }

  function feedbackRows() {
    const list = filteredFeedback();
    if (!list.length) return `<tr><td colspan="6" class="muted center">${esc(t("fbEmpty"))}</td></tr>`;
    return list.map((f) => {
      const expanded = state.fbExpanded.has(f.id);
      const long = f.message.length > 180 || f.message.split("\n").length > 3;
      return `
        <tr class="fb-row fb-row-${esc(f.status)}">
          <td class="num fb-date">${esc(fmtDateTime(f.created_at))}</td>
          <td><span class="fb-badge fb-badge-${esc(f.category)}">${icon(FB_ICONS[f.category] || "message")}<span>${esc(t(`fbCat_${f.category}`))}</span></span></td>
          <td>
            <div class="row-title">${f.user_name ? bdi(f.user_name) : `<span class="muted">${esc(t("fbGuest"))}</span>`}</div>
            <div class="row-sub">${esc([f.username, f.ip].filter(Boolean).join(" · "))}</div>
          </td>
          <td class="fb-content">
            <div class="fb-subject">${bdi(f.subject)}</div>
            <div class="fb-message ${expanded ? "expanded" : ""}">${esc(f.message)}</div>
            ${long ? `<button class="link-btn" type="button" data-action="fb-expand" data-id="${f.id}">${esc(expanded ? t("showLess") : t("showMore"))}</button>` : ""}
          </td>
          <td>
            <select class="select fb-status fb-status-${esc(f.status)}" data-feedback-status data-id="${f.id}" aria-label="${esc(t("colStatus"))}">
              ${FB_STATUSES.map((s) => `<option value="${s}"${s === f.status ? " selected" : ""}>${esc(t(`fbStatus_${s}`))}</option>`).join("")}
            </select>
          </td>
          <td class="actions-cell">
            <button class="icon-btn icon-btn-sm" type="button" data-action="delete-feedback" data-id="${f.id}" title="${esc(t("delete"))}" aria-label="${esc(t("delete"))}">${icon("trash")}</button>
          </td>
        </tr>`;
    }).join("");
  }

  function renderFeedback() {
    const counts = state.feedback.counts;
    const total = FB_STATUSES.reduce((sum, s) => sum + (counts[s] || 0), 0);
    const statusTabs = ["all", ...FB_STATUSES].map((s) => `
      <button type="button" class="${state.fbStatus === s ? "active" : ""}" data-action="fb-status-filter" data-status="${s}">
        ${esc(s === "all" ? t("fbAll") : t(`fbStatus_${s}`))}<span class="seg-count">${s === "all" ? total : counts[s] || 0}</span>
      </button>`).join("");
    const categorySelect = `
      <select class="select" id="fb-category-filter" aria-label="${esc(t("colType"))}">
        <option value="all">${esc(t("fbAllCategories"))}</option>
        ${FB_CATEGORIES.map((c) => `<option value="${c}"${state.fbCategory === c ? " selected" : ""}>${esc(t(`fbCat_${c}`))}</option>`).join("")}
      </select>`;
    return `
      ${pageHead(t("navFeedback"), t("feedbackSubtitle"), `${categorySelect}<div class="segmented">${statusTabs}</div>`)}
      <div class="table-wrap card">
        <table class="table fb-table">
          <thead><tr><th>${esc(t("colDate"))}</th><th>${esc(t("colType"))}</th><th>${esc(t("colSender"))}</th><th>${esc(t("colContent"))}</th><th>${esc(t("colStatus"))}</th><th></th></tr></thead>
          <tbody>${feedbackRows()}</tbody>
        </table>
      </div>`;
  }

  async function updateFeedbackStatus(select) {
    const id = Number(select.dataset.id);
    select.disabled = true;
    try {
      const updated = await api("PATCH", `/api/admin/feedback/${id}`, { status: select.value });
      toast(t("fbStatusSaved", t(`fbStatus_${updated.status}`)), "success");
      await reload("feedback", "overview");
    } catch (err) {
      fail(err);
      render();
    }
  }

  // ------------------------------------------------------ Authentication

  // Field definitions per subsection. `env` is the matching environment variable (shown as a badge).
  const AUTH_CARDS = [
    {
      section: "keycloak", icon: "shield", tests: ["keycloak"],
      fields: [
        { k: "enabled", env: "KEYCLOAK_ENABLED", type: "toggle" },
        { k: "tls_insecure", env: "KEYCLOAK_TLS_INSECURE", type: "toggle" },
        { k: "url", env: "KEYCLOAK_URL", type: "url", placeholder: "https://keycloak.example.com" },
        { k: "realm", env: "KEYCLOAK_REALM", placeholder: "master" },
        { k: "client_id", env: "KEYCLOAK_CLIENT_ID", placeholder: "pakal" },
        { k: "client_secret", env: "KEYCLOAK_CLIENT_SECRET", type: "secret" },
        { k: "redirect_uri", env: "KEYCLOAK_REDIRECT_URI", type: "url", wide: true },
        { k: "post_logout_redirect_uri", env: "KEYCLOAK_POST_LOGOUT_REDIRECT_URI", type: "url", wide: true },
        { k: "cooldown_after_logout_ms", env: "KEYCLOAK_SSO_COOLDOWN_AFTER_LOGOUT_MS", type: "number", min: 0, max: 600000, step: 500, unit: "ms" },
        { k: "timeout_ms", env: "KEYCLOAK_TIMEOUT_MS", type: "number", min: 500, max: 60000, step: 500, unit: "ms" },
        { k: "admin_role", env: "KEYCLOAK_ADMIN_ROLE", placeholder: "admin" },
        { k: "idp_hint", env: "KEYCLOAK_IDP_HINT", optional: true },
        { k: "prompt", env: "KEYCLOAK_PROMPT", type: "select", options: ["", "login", "consent", "select_account", "none"], optional: true },
        { k: "extra_scopes", env: "KEYCLOAK_EXTRA_SCOPES", optional: true, placeholder: "roles" },
      ],
    },
    {
      section: "ldap_server", icon: "server", tests: ["ldap"],
      fields: [
        { k: "url", env: "LDAP_URL", placeholder: "ldap://dc01.example.com:389", wide: true },
        { k: "search_base", env: "LDAP_SEARCH_BASE", placeholder: "DC=example,DC=com", wide: true },
        { k: "bind_dn", env: "LDAP_ADMIN", placeholder: "CN=svc_account,OU=Service Accounts,…", wide: true },
        { k: "bind_password", env: "LDAP_PASSWORD", type: "secret" },
      ],
    },
    {
      section: "ldap_groups", icon: "user",
      fields: [
        { k: "admin_group_dn", env: "LDAP_ADMIN_GROUP_DN", placeholder: "CN=Domain Admins,CN=Users,DC=example,DC=com", wide: true },
        { k: "netbios_domain", env: "LDAP_NETBIOS_DOMAIN", optional: true, placeholder: "CORP" },
      ],
    },
    {
      section: "ldap_lookup", icon: "search", tests: ["lookup"],
      fields: [
        { k: "enabled", env: "LDAP_DISPLAY_NAME_LOOKUP", type: "toggle" },
        { k: "timeout_ms", env: "LDAP_LOOKUP_TIMEOUT_MS", type: "number", min: 100, max: 30000, step: 100, unit: "ms" },
        { k: "pause_sec", env: "LDAP_DISPLAY_NAME_PAUSE_SEC", type: "number", min: 0, max: 86400, step: 10, unit: "sec" },
      ],
    },
    {
      section: "login_identity", icon: "login",
      fields: [{ k: "email_domain", env: "USER_EMAIL_DOMAIN", placeholder: "example.com" }],
    },
    {
      section: "local_admin", icon: "lock",
      fields: [
        { k: "username", env: "LOCAL_ADMIN_USERNAME", placeholder: "pakal" },
        { k: "password", env: "LOCAL_ADMIN_PASSWORD", type: "new-password" },
        { k: "password_confirm", type: "confirm" },
      ],
    },
  ];
  const NEXUS_CARD = {
    section: "nexus", icon: "package", tests: ["nexus"],
    fields: [
      { k: "enabled", env: "NEXUS_ENABLED", type: "toggle" },
      { k: "check_existing", env: "NEXUS_CHECK_EXISTING", type: "toggle" },
      { k: "tls_insecure", env: "NEXUS_TLS_INSECURE", type: "toggle" },
      { k: "url", env: "NEXUS_URL", type: "url", placeholder: "https://nexus.example.com", wide: true },
      { k: "username", env: "NEXUS_USERNAME", placeholder: "svc_account" },
      { k: "password", env: "NEXUS_PASSWORD", type: "secret" },
      { k: "pypi_repo", env: "NEXUS_PYPI_REPO", placeholder: "pypi-hosted" },
      { k: "npm_repo", env: "NEXUS_NPM_REPO", placeholder: "npm-hosted" },
      { k: "powershell_repo", env: "NEXUS_POWERSHELL_REPO", placeholder: "powershell-hosted" },
      { k: "max_upload_mb", env: "NEXUS_MAX_UPLOAD_MB", type: "number", min: 1, max: 10240, step: 1, unit: "mb" },
      { k: "timeout_seconds", env: "NEXUS_TIMEOUT_SECONDS", type: "number", min: 5, max: 3600, step: 5, unit: "sec" },
    ],
  };
  const DOCKER_CARD = {
    section: "docker", icon: "server", tests: ["docker"],
    fields: [
      { k: "enabled", type: "toggle" },
      { k: "build_enabled", env: "DOCKER_BUILD_ENABLED", type: "toggle" },
      { k: "build_admin_only", env: "DOCKER_BUILD_ADMIN_ONLY", type: "toggle" },
      { k: "tls_insecure", env: "NEXUS_TLS_INSECURE", type: "toggle" },
      { k: "registry", env: "NEXUS_DOCKER_REGISTRY", placeholder: "nexus.example.com:5000", wide: true },
      { k: "username", env: "NEXUS_DOCKER_USERNAME", optional: true, placeholder: "svc_account" },
      { k: "password", env: "NEXUS_DOCKER_PASSWORD", type: "secret" },
      { k: "namespace", env: "NEXUS_DOCKER_NAMESPACE", optional: true, placeholder: "pakal" },
      { k: "max_context_mb", env: "DOCKER_MAX_CONTEXT_MB", type: "number", min: 1, max: 20480, step: 1, unit: "mb" },
      { k: "build_timeout_seconds", env: "DOCKER_BUILD_TIMEOUT_SECONDS", type: "number", min: 60, max: 86400, step: 60, unit: "sec" },
    ],
  };
  const ALL_CARDS = [...AUTH_CARDS, NEXUS_CARD, DOCKER_CARD];
  const UNIT_LABELS = { ms: "msUnit", sec: "secondsUnit", mb: "mbUnit" };

  const authLabel = (section, k) => t(`f_${section}_${k}`);
  const authHint = (section, k) => {
    const value = I18N[state.lang][`h_${section}_${k}`] ?? I18N.he[`h_${section}_${k}`];
    return typeof value === "function" ? value() : value || "";
  };

  function authValueHint(card, f, value) {
    const def = state.auth.defaults[card.section][f.k];
    if (f.type === "toggle" || f.type === "secret" || f.type === "new-password" || f.type === "confirm") return "";
    if (def === undefined || def === "" || String(def) === String(value ?? "")) return "";
    return t("defaultValue", def);
  }

  function authField(card, f) {
    const s = state.auth.sections[card.section];
    const value = s[f.k];
    const name = `${card.section}.${f.k}`;
    const envBadge = f.env ? `<code class="env-key" dir="ltr">${esc(f.env)}</code>` : "";
    const optional = f.optional ? `<span class="opt-tag">${esc(t("optional"))}</span>` : "";
    const hint = [authHint(card.section, f.k), authValueHint(card, f, value)].filter(Boolean);
    const hintHtml = hint.length ? `<span class="hint">${hint.map(esc).join(" · ")}</span>` : "";
    const err = `<span class="field-error" data-error-for="${esc(f.k)}"></span>`;
    const head = `<span class="auth-label"><span>${esc(authLabel(card.section, f.k))}</span>${optional}${envBadge}</span>`;

    if (f.type === "toggle") {
      return `
        <label class="switch-row auth-toggle wide">
          <span class="switch"><input type="checkbox" name="${esc(f.k)}"${value ? " checked" : ""}><span class="switch-track"></span></span>
          <span class="switch-text">${head}${hintHtml}</span>
        </label>`;
    }
    let control;
    if (f.type === "secret") {
      const has = s[`has_${f.k}`];
      control = `
        <input class="input mono" name="${esc(f.k)}" type="password" dir="ltr" autocomplete="new-password" spellcheck="false"
          placeholder="${esc(has ? t("secretStored") : t("secretNotSet"))}">
        ${has ? `<label class="check"><input type="checkbox" name="clear_${esc(f.k)}"><span>${esc(t("clearSecret"))}</span></label>` : ""}`;
    } else if (f.type === "new-password") {
      control = `<input class="input mono" name="${esc(f.k)}" type="password" dir="ltr" autocomplete="new-password" minlength="8"
          placeholder="${esc(s.has_password ? t("secretStored") : t("secretNotSet"))}">`;
      hint.unshift(s.password_source === "database" ? t("pwFromDb") : t("pwFromEnv"));
    } else if (f.type === "confirm") {
      control = `<input class="input mono" name="${esc(f.k)}" type="password" dir="ltr" autocomplete="new-password">`;
    } else if (f.type === "select") {
      control = `<select class="input mono" name="${esc(f.k)}" dir="ltr">${f.options.map((o) => `<option value="${esc(o)}"${o === (value || "") ? " selected" : ""}>${esc(o || t("promptDefault"))}</option>`).join("")}</select>`;
    } else if (f.type === "number") {
      control = `<span class="input-suffix" dir="ltr"><input class="input mono" name="${esc(f.k)}" type="number" inputmode="numeric" min="${f.min}" max="${f.max}" step="${f.step}" value="${esc(value ?? "")}"><span class="suffix">${esc(t(UNIT_LABELS[f.unit] || "secondsUnit"))}</span></span>`;
    } else {
      control = `<input class="input mono" name="${esc(f.k)}" type="${f.type === "url" ? "url" : "text"}" dir="ltr" autocomplete="off" spellcheck="false" value="${esc(value ?? "")}"${f.placeholder ? ` placeholder="${esc(f.placeholder)}"` : ""}>`;
    }
    const finalHint = hint.length ? `<span class="hint">${hint.map(esc).join(" · ")}</span>` : "";
    return `<div class="field auth-field${f.wide ? " wide" : ""}" data-field="${esc(name)}">${head}${control}${finalHint}${err}</div>`;
  }

  function keycloakExtras() {
    const eps = state.auth.keycloak_endpoints || {};
    const rows = [["auth", "Authorization"], ["token", "Token"], ["userinfo", "Userinfo"], ["logout", "Logout"]]
      .map(([k, label]) => `<dt>${esc(label)}</dt><dd class="mono" dir="ltr">${esc(eps[k] || "—")}</dd>`).join("");
    return `
      <div class="auth-derived wide">
        <div class="auth-derived-title">${esc(t("derivedEndpoints"))}</div>
        <dl class="kv kv-compact">${rows}<dt>${esc(t("requestedScopes"))}</dt><dd class="mono" dir="ltr">${esc(state.auth.keycloak_scopes)}</dd></dl>
      </div>`;
  }

  function testResult(kind) {
    const r = state.authTests[kind];
    if (!r) return "";
    if (kind === "keycloak") {
      const names = { auth: "Authorization", token: "Token", userinfo: "Userinfo", logout: "Logout" };
      return `
        <div class="auth-test ${r.ok ? "ok" : "bad"} wide">
          <strong>${esc(r.ok ? t("ssoTestOk") : t("ssoTestFail"))}</strong>
          <dl class="kv kv-compact">${Object.entries(r.results).map(([k, x]) => `
            <dt>${esc(names[k] || k)}</dt>
            <dd><span class="status-dot ${x.ok ? "" : "bad"}"></span>${esc(x.ok ? t("reachable") : t("unreachable"))}
              <span class="mono subtle" dir="ltr">${esc([x.status ? `HTTP ${x.status}` : "", x.error, `${x.ms} ms`].filter(Boolean).join(" · "))}</span></dd>`).join("")}
          </dl>
        </div>`;
    }
    if (kind === "nexus") {
      const repoState = (x) => (x.ok ? t("repoOk") : x.found ? t("repoWrong", x.format || "?", x.type || "?") : t("repoMissing"));
      const flag = (value) => `<span class="status-dot ${value ? "" : "bad"}"></span>${esc(value ? t("yes") : value === false ? t("no") : "—")}`;
      return `
        <div class="auth-test ${r.ok ? "ok" : "bad"} wide">
          <strong>${esc(r.ok ? t("nexusTestOk") : t("nexusTestFail"))}</strong>
          <dl class="kv kv-compact">
            <dt>${esc(t("nexusReachable"))}</dt><dd>${flag(r.reachable)}</dd>
            <dt>${esc(t("nexusAuth"))}</dt><dd>${flag(r.auth)}</dd>
            ${(r.repos || []).map((x) => `
              <dt><span dir="ltr">${esc(x.name)}</span></dt>
              <dd><span class="status-dot ${x.ok ? "" : "bad"}"></span>${esc(repoState(x))} <span class="mono subtle">${esc(x.kind)}</span></dd>`).join("")}
            ${r.error ? `<dt>${esc(t("error"))}</dt><dd class="mono" dir="ltr">${esc(r.error)}</dd>` : ""}
            <dt>${esc(t("duration"))}</dt><dd class="mono">${esc(r.ms)} ms</dd>
          </dl>
        </div>`;
    }
    if (kind === "docker") {
      const flag = (value) => `<span class="status-dot ${value ? "" : "bad"}"></span>${esc(value ? t("yes") : value === false ? t("no") : "—")}`;
      const engine = r.engine || {};
      return `
        <div class="auth-test ${r.ok ? "ok" : "bad"} wide">
          <strong>${esc(r.ok ? t("dockerTestOk") : t("dockerTestFail"))}</strong>
          <dl class="kv kv-compact">
            <dt>${esc(t("nexusReachable"))}</dt><dd>${flag(r.reachable)}</dd>
            <dt>${esc(t("nexusAuth"))}</dt><dd>${flag(r.auth)}</dd>
            ${r.ok ? `<dt>${esc(t("dockerRepos"))}</dt><dd class="mono">${esc(r.repositories)}</dd>` : ""}
            ${r.error ? `<dt>${esc(t("error"))}</dt><dd class="mono" dir="ltr">${esc(r.error)}</dd>` : ""}
            <dt>${esc(t("dockerEngine"))}</dt><dd>${flag(engine.available)} <span class="mono subtle" dir="ltr">${esc(engine.available ? `Docker ${engine.version} · API ${engine.api}` : engine.error || "")}</span></dd>
            <dt>${esc(t("duration"))}</dt><dd class="mono">${esc(r.ms)} ms</dd>
          </dl>
        </div>`;
    }
    if (kind === "ldap") {
      return `
        <div class="auth-test ${r.ok ? "ok" : "bad"} wide">
          <strong>${esc(r.ok ? t("ldapTestOk") : t("ldapTestFail"))}</strong>
          <dl class="kv kv-compact">
            <dt>${esc(t("ldapServers"))}</dt><dd class="mono" dir="ltr">${esc((r.servers || []).join(", ") || "—")}</dd>
            <dt>${esc(t("ldapBind"))}</dt><dd><span class="status-dot ${r.bind ? "" : "bad"}"></span>${esc(r.bind ? t("yes") : t("no"))}</dd>
            <dt>${esc(t("ldapBase"))}</dt><dd><span class="status-dot ${r.base_found ? "" : "bad"}"></span>${esc(r.base_found ? t("yes") : t("no"))}</dd>
            ${r.error ? `<dt>${esc(t("error"))}</dt><dd class="mono" dir="ltr">${esc(r.error)}</dd>` : ""}
            <dt>${esc(t("duration"))}</dt><dd class="mono">${esc(r.ms)} ms</dd>
          </dl>
        </div>`;
    }
    const u = r.user;
    return `
      <div class="auth-test ${r.found ? "ok" : "bad"} wide">
        <strong>${esc(r.found ? t("lookupFound") : r.error ? t("lookupError") : t("lookupNotFound"))}</strong>
        <dl class="kv kv-compact">
          ${u ? `<dt>${esc(t("displayName"))}</dt><dd>${bdi(u.name)}</dd>
          <dt>sAMAccountName</dt><dd class="mono" dir="ltr">${esc(u.username)}</dd>
          <dt>Email</dt><dd class="mono" dir="ltr">${esc(u.email || "—")}</dd>
          <dt>DN</dt><dd class="mono" dir="ltr">${esc(u.dn || "—")}</dd>
          <dt>${esc(t("adminGroupMember"))}</dt><dd>${esc(u.admin ? t("yes") : t("no"))}</dd>` : ""}
          ${r.error ? `<dt>${esc(t("error"))}</dt><dd class="mono" dir="ltr">${esc(r.error)}</dd>` : ""}
          <dt>${esc(t("duration"))}</dt><dd class="mono">${esc(r.ms)} ms</dd>
        </dl>
      </div>`;
  }

  function testButtons(card) {
    return (card.tests || []).map((kind) => {
      if (kind === "lookup") {
        return `
          <span class="lookup-test">
            <input class="input input-sm mono" id="lookup-username" dir="ltr" placeholder="${esc(t("lookupPlaceholder"))}" autocomplete="off" spellcheck="false" maxlength="120">
            <button class="btn btn-secondary btn-sm" type="button" data-action="auth-test" data-kind="lookup">${icon("search")}<span>${esc(t("lookupTest"))}</span></button>
          </span>`;
      }
      return `<button class="btn btn-secondary btn-sm" type="button" data-action="auth-test" data-kind="${kind}">${icon("activity")}<span>${esc(t({ keycloak: "ssoTest", nexus: "nexusTest", docker: "nexusTest" }[kind] || "ldapTest"))}</span></button>`;
    }).join("");
  }

  function saveStatus(section) {
    const st = state.authStatus[section];
    if (!st) return `<span class="save-status" role="status" aria-live="polite"></span>`;
    const iconName = st.kind === "saving" ? "refresh" : st.kind === "ok" ? "check" : "alert";
    return `<span class="save-status is-${st.kind}" role="status" aria-live="polite">${icon(iconName)}<span>${esc(st.message)}</span></span>`;
  }

  function renderAuthCard(card) {
    const stored = state.auth.stored[card.section];
    const extras = card.section === "keycloak" ? keycloakExtras() : "";
    const tests = (card.tests || []).map(testResult).join("");
    return `
      <form class="card panel auth-card" id="auth-${card.section}" data-section="${card.section}" novalidate autocomplete="off">
        <div class="panel-head">
          <div class="auth-card-title">
            <span class="glyph-tile auth-glyph">${icon(card.icon)}</span>
            <div><h3>${esc(t(`card_${card.section}`))}</h3><p>${esc(t(`card_${card.section}_sub`))}</p></div>
          </div>
          <span class="badge ${stored ? "badge-accent" : ""}" title="${esc(t(stored ? "sourceDbHint" : "sourceEnvHint"))}">${esc(t(stored ? "sourceDb" : "sourceEnv"))}</span>
        </div>
        <div class="auth-grid">
          ${card.fields.map((f) => authField(card, f)).join("")}
          ${extras}
        </div>
        ${card.section === "keycloak" ? `<p class="auth-note">${esc(t("keycloakNote"))}</p>` : ""}
        ${card.section === "local_admin" ? `<p class="auth-note">${esc(t("localAdminNote"))}</p>` : ""}
        ${card.section === "nexus" ? `<p class="auth-note">${esc(t("nexusNote"))}</p>` : ""}
        ${card.section === "docker" ? `<p class="auth-note">${esc(t("dockerNote"))}</p>` : ""}
        ${tests}
        <div class="auth-foot">
          ${saveStatus(card.section)}
          <span class="auth-foot-actions">
            ${testButtons(card)}
            ${stored ? `<button class="btn btn-ghost btn-sm" type="button" data-action="auth-reset" data-section="${card.section}">${icon("refresh")}<span>${esc(t("ssoReset"))}</span></button>` : ""}
            <button class="btn btn-primary btn-sm" type="button" data-action="auth-save" data-section="${card.section}">${icon("check")}<span>${esc(t("saveSection"))}</span></button>
          </span>
        </div>
      </form>`;
  }

  function renderSso() {
    if (!state.auth) return "";
    const kc = AUTH_CARDS.slice(0, 1).map(renderAuthCard).join("");
    const ldap = AUTH_CARDS.slice(1, 5).map(renderAuthCard).join("");
    const local = AUTH_CARDS.slice(5).map(renderAuthCard).join("");
    const lookup = state.auth.lookup || {};
    return `
      ${pageHead(t("navSso"), t("ssoSubtitle"))}
      <h2 class="auth-group-title">${icon("shield")}<span>${esc(t("groupKeycloak"))}</span></h2>
      ${kc}
      <h2 class="auth-group-title">${icon("server")}<span>${esc(t("groupLdap"))}</span>
        <span class="badge ${state.auth.ldap_configured ? "badge-accent" : ""}">${esc(state.auth.ldap_configured ? t("ssoStatusOn") : t("ssoStatusOff"))}</span>
        ${lookup.paused_for_sec ? `<span class="badge badge-danger">${esc(t("lookupPaused", lookup.paused_for_sec))}</span>` : ""}
      </h2>
      <div class="auth-cards">${ldap}</div>
      <h2 class="auth-group-title">${icon("lock")}<span>${esc(t("groupLocal"))}</span></h2>
      ${local}`;
  }

  function renderNexus() {
    if (!state.auth || !state.auth.sections.nexus) return "";
    const docker = state.auth.sections.docker ? renderAuthCard(DOCKER_CARD) : "";
    return `${pageHead(t("navNexus"), t("nexusSubtitle"))}<div class="auth-cards">${renderAuthCard(NEXUS_CARD)}${docker}</div>`;
  }

  function rerenderAuthCard(section) {
    const card = ALL_CARDS.find((c) => c.section === section);
    const form = $(`#auth-${section}`);
    if (!card || !form) return;
    form.outerHTML = renderAuthCard(card);
  }

  function readAuthCard(section) {
    const form = $(`#auth-${section}`);
    const card = ALL_CARDS.find((c) => c.section === section);
    const body = {};
    for (const f of card.fields) {
      const el = form.elements[f.k];
      if (f.type === "toggle") body[f.k] = el.checked;
      else if (f.type === "number") body[f.k] = el.value === "" ? null : Number(el.value);
      else if (f.type === "secret") {
        if (el.value.trim()) body[f.k] = el.value;
        body[`clear_${f.k}`] = Boolean(form.elements[`clear_${f.k}`] && form.elements[`clear_${f.k}`].checked);
      } else if (f.type === "new-password") {
        if (el.value) body[f.k] = el.value;
      } else if (f.type === "confirm") {
        // compared client-side only
      } else body[f.k] = el.value.trim();
    }
    return body;
  }

  function setFieldErrors(section, errors) {
    const form = $(`#auth-${section}`);
    if (!form) return;
    $$(".field-error", form).forEach((el) => { el.textContent = ""; });
    $$(".auth-field.has-error", form).forEach((el) => el.classList.remove("has-error"));
    Object.entries(errors).forEach(([k, msg]) => {
      const el = $(`[data-error-for="${k}"]`, form);
      if (!el) return;
      el.textContent = msg;
      el.closest(".auth-field").classList.add("has-error");
    });
  }

  function setAuthStatus(section, kind, message) {
    state.authStatus[section] = { kind, message };
    const form = $(`#auth-${section}`);
    const slot = form && $(".save-status", form);
    if (slot) slot.outerHTML = saveStatus(section);
  }

  async function saveAuthSection(section, button) {
    const form = $(`#auth-${section}`);
    const body = readAuthCard(section);
    if (section === "local_admin") {
      const pw = form.elements.password.value;
      if (pw && pw !== form.elements.password_confirm.value) {
        setFieldErrors(section, { password_confirm: t("pwMismatch") });
        setAuthStatus(section, "error", t("fixErrors"));
        return;
      }
      if (pw && pw.length < 8) {
        setFieldErrors(section, { password: t("pwTooShort") });
        setAuthStatus(section, "error", t("fixErrors"));
        return;
      }
    }
    setFieldErrors(section, {});
    setAuthStatus(section, "saving", t("savingSection"));
    button.disabled = true;
    try {
      const res = await fetch(`/api/admin/auth/${section}`, {
        method: "PUT", credentials: "same-origin", cache: "no-store",
        headers: { ...CSRF_HEADERS, "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      if (res.status === 401) { showLogin(t("sessionExpired")); return; }
      const parsed = await res.json().catch(() => null);
      if (!res.ok) {
        const detail = parsed && parsed.detail;
        if (Array.isArray(detail)) {
          const errors = {};
          detail.forEach((e) => {
            const key = (e.loc || [])[1] || "";
            errors[key] = String(e.msg || "").replace(/^Value error, /, "");
          });
          setFieldErrors(section, errors);
          setAuthStatus(section, "error", t("fixErrors"));
        } else {
          setAuthStatus(section, "error", typeof detail === "string" ? detail : `${t("requestFailed")} (${res.status})`);
        }
        return;
      }
      state.auth = parsed;
      const staleTests = { keycloak: ["keycloak"], nexus: ["nexus"], docker: ["docker"] }[section] || ["ldap", "lookup"];
      staleTests.forEach((k) => { state.authTests[k] = null; });
      state.authStatus[section] = { kind: "ok", message: t("sectionSaved", new Date().toLocaleTimeString(state.lang === "he" ? "he-IL" : "en-GB")) };
      rerenderAuthCard(section);
      if (section === "keycloak") updateSsoDot();
      if (section === "nexus") updateNexusDot();
      toast(t("sectionSavedToast", t(`card_${section}`)), "success");
    } catch (err) {
      setAuthStatus(section, "error", err.message || t("requestFailed"));
    } finally {
      const b = $(`#auth-${section} [data-action="auth-save"]`);
      if (b) b.disabled = false;
    }
  }

  async function resetAuthSection(section) {
    if (!(await confirmDialog(t("confirmSectionReset", t(`card_${section}`)), t("confirmSsoResetText"), t("ssoReset")))) return;
    state.auth = await api("POST", `/api/admin/auth/${section}/reset`);
    state.authStatus[section] = { kind: "ok", message: t("ssoResetDone") };
    rerenderAuthCard(section);
    if (section === "keycloak") updateSsoDot();
    if (section === "nexus") updateNexusDot();
    toast(t("ssoResetDone"), "success");
  }

  async function runAuthTest(kind, button) {
    const section = { keycloak: "keycloak", ldap: "ldap_server", lookup: "ldap_lookup", nexus: "nexus", docker: "docker" }[kind];
    const label = button.querySelector("span");
    const original = label.textContent;
    let body;
    if (kind === "lookup") {
      const username = ($("#lookup-username").value || "").trim();
      if (!username) { $("#lookup-username").focus(); return; }
      body = { username };
    } else if (kind === "nexus" || kind === "docker") {
      body = readAuthCard(kind);
      setFieldErrors(kind, {});
    }
    button.disabled = true;
    label.textContent = t("ssoTesting");
    try {
      const url = {
        keycloak: "/api/admin/auth/keycloak/test", ldap: "/api/admin/auth/ldap/test",
        lookup: "/api/admin/auth/ldap/lookup", nexus: "/api/admin/nexus/test", docker: "/api/admin/docker/test",
      }[kind];
      state.authTests[kind] = await api("POST", url, body);
      const lookupValue = kind === "lookup" ? body.username : null;
      if (kind === "nexus" || kind === "docker") {
        // In place, so unsaved form values stay in the inputs.
        const form = $(`#auth-${kind}`);
        $$(".auth-test", form).forEach((el) => el.remove());
        $(".auth-foot", form).insertAdjacentHTML("beforebegin", testResult(kind));
      } else rerenderAuthCard(section);
      if (lookupValue) $("#lookup-username").value = lookupValue;
      const r = state.authTests[kind];
      const ok = kind === "lookup" ? r.found : r.ok;
      toast(t(ok ? "testPassed" : "testFailed"), ok ? "success" : "error", 5000);
    } catch (err) {
      fail(err);
    } finally {
      const b = $(`#auth-${section} [data-action="auth-test"][data-kind="${kind}"]`);
      if (b) { b.disabled = false; const s = b.querySelector("span"); if (s) s.textContent = original; }
    }
  }

  function updateNexusDot() {
    const cfg = state.auth && state.auth.sections.nexus;
    const on = Boolean(cfg && cfg.enabled && cfg.url);
    $("#nexus-dot").className = `sso-dot ${on ? "on" : ""}`;
    $("#nexus-dot").title = on ? t("ssoStatusOn") : t("ssoStatusOff");
  }

  // ------------------------------------------------------ Portal interface

  const UI_GROUPS = ["tabs", "header", "content"];
  const hiddenCount = (values) => Object.values(values || {}).filter((v) => !v).length;
  const uiDirty = () => Boolean(state.ui) && state.ui.elements.some(({ key }) => state.uiDraft[key] !== state.ui.visibility[key]);

  function updateHiddenCount() {
    const badge = $("#count-hidden-ui");
    const n = state.ui ? hiddenCount(state.ui.visibility) : 0;
    badge.hidden = !n;
    badge.textContent = n || "";
    badge.title = t("uiHiddenCount", n);
  }

  function uiFoot() {
    const dirty = uiDirty();
    const status = dirty
      ? `<span class="save-status ui-unsaved" role="status">${icon("alert")}<span>${esc(t("uiUnsaved"))}</span></span>`
      : `<span class="save-status" role="status">${esc(t("uiHiddenCount", hiddenCount(state.ui.visibility)))}</span>`;
    return `
      <div class="auth-foot ui-foot" id="ui-foot">
        ${status}
        <span class="auth-foot-actions">
          ${hiddenCount(state.uiDraft) ? `<button class="btn btn-ghost btn-sm" type="button" data-action="ui-show-all">${icon("eye")}<span>${esc(t("uiShowAll"))}</span></button>` : ""}
          ${state.ui.stored ? `<button class="btn btn-ghost btn-sm" type="button" data-action="ui-reset">${icon("refresh")}<span>${esc(t("ssoReset"))}</span></button>` : ""}
          <button class="btn btn-primary btn-sm" type="button" data-action="ui-save"${dirty ? "" : " disabled"}>${icon("check")}<span>${esc(t("uiSave"))}</span></button>
        </span>
      </div>`;
  }

  function uiRow(key) {
    const on = state.uiDraft[key] !== false;
    const changed = on !== (state.ui.visibility[key] !== false);
    return `
      <label class="switch-row ui-row${on ? "" : " is-off"}${changed ? " is-changed" : ""}">
        <span class="switch"><input type="checkbox" data-ui-key="${esc(key)}"${on ? " checked" : ""}><span class="switch-track"></span></span>
        <span class="switch-text">
          <span class="ui-row-title">${esc(t(`ui_${key}`))}<code class="env-key" dir="ltr">${esc(key)}</code></span>
          <span class="hint">${esc(t(`uid_${key}`))}</span>
        </span>
        <span class="badge ui-state ${on ? "" : "badge-danger"}">${icon(on ? "eye" : "eyeOff")}<span>${esc(t(on ? "uiShown" : "uiHidden"))}</span></span>
      </label>`;
  }

  function renderInterface() {
    if (!state.ui) return "";
    const groups = UI_GROUPS.map((group) => {
      const keys = state.ui.elements.filter((e) => e.group === group).map((e) => e.key);
      if (!keys.length) return "";
      return `
        <section class="card panel ui-group">
          <div class="panel-head"><div><h3>${esc(t(`uiGroup_${group}`))}</h3><p>${esc(t(`uiGroupSub_${group}`))}</p></div></div>
          <div class="ui-rows">${keys.map(uiRow).join("")}</div>
        </section>`;
    }).join("");
    return `
      ${pageHead(t("navInterface"), t("interfaceSubtitle"))}
      ${announcementCard()}
      <div id="ui-groups">${groups}</div>
      <div class="card panel ui-foot-card">${uiFoot()}</div>`;
  }

  // ------------------------------------------------------- announcement card

  const ANN_SEVERITIES = ["info", "success", "warning", "danger"];
  const ANN_ICONS = { info: "message", success: "check", warning: "alert", danger: "alert" };
  const ANN_FIELDS = ["enabled", "severity", "title", "message"];
  const annDirty = () => Boolean(state.announcement) && ANN_FIELDS.some((k) => state.annDraft[k] !== state.announcement[k]);

  function annPreview() {
    const d = state.annDraft;
    return `
      <div class="ann-preview sev-${esc(d.severity)}${d.enabled ? "" : " is-off"}" id="ann-preview" aria-hidden="true">
        <span class="ann-preview-icon">${icon(ANN_ICONS[d.severity] || "message")}</span>
        <div class="ann-preview-body">
          <span class="ann-preview-kicker">${esc(t(`annSev_${d.severity}`))}</span>
          ${d.title.trim() ? `<strong>${esc(d.title)}</strong>` : ""}
          <p>${d.message.trim() ? esc(d.message) : `<span class="subtle">${esc(t("annEmpty"))}</span>`}</p>
        </div>
        ${icon("x")}
      </div>`;
  }

  function annFoot() {
    const a = state.announcement;
    const dirty = annDirty();
    const live = a.enabled && a.message;
    const status = dirty
      ? `<span class="save-status ui-unsaved" role="status">${icon("alert")}<span>${esc(t("uiUnsaved"))}</span></span>`
      : `<span class="save-status" role="status">${esc(live ? t("annLive", a.revision) : t("annOff"))}</span>`;
    return `
      <div class="auth-foot ui-foot" id="ann-foot">
        ${status}
        <span class="auth-foot-actions">
          ${live && !dirty ? `<button class="btn btn-ghost btn-sm" type="button" data-action="ann-republish" title="${esc(t("annRepublishHint"))}">${icon("refresh")}<span>${esc(t("annRepublish"))}</span></button>` : ""}
          <button class="btn btn-primary btn-sm" type="button" data-action="ann-save"${dirty ? "" : " disabled"}>${icon("check")}<span>${esc(t("annSave"))}</span></button>
        </span>
      </div>`;
  }

  function announcementCard() {
    if (!state.announcement) return "";
    const d = state.annDraft;
    return `
      <section class="card panel ann-card" id="ann-card">
        <div class="panel-head"><div><h3>${esc(t("annTitle"))}</h3><p>${esc(t("annSubtitle"))}</p></div></div>
        <div class="ann-layout">
          <div class="ann-form">
            <label class="switch-row">
              <span class="switch"><input type="checkbox" id="ann-enabled"${d.enabled ? " checked" : ""}><span class="switch-track"></span></span>
              <span class="switch-text"><span class="ui-row-title">${esc(t("annEnabled"))}</span><span class="hint">${esc(t("annEnabledHint"))}</span></span>
            </label>
            <div class="ann-row">
              <label class="field"><span class="label">${esc(t("annSeverity"))}</span>
                <select class="select" id="ann-severity">${ANN_SEVERITIES.map((s) => `<option value="${s}"${s === d.severity ? " selected" : ""}>${esc(t(`annSev_${s}`))}</option>`).join("")}</select>
              </label>
              <label class="field ann-grow"><span class="label">${esc(t("annTitleField"))}</span>
                <input class="input" id="ann-title" maxlength="120" value="${esc(d.title)}" placeholder="${esc(t("annTitlePh"))}">
              </label>
            </div>
            <label class="field"><span class="label">${esc(t("annMessage"))} <span class="subtle mono" id="ann-count" dir="ltr">${d.message.length} / 1000</span></span>
              <textarea class="textarea" id="ann-message" rows="4" maxlength="1000" placeholder="${esc(t("annMessagePh"))}">${esc(d.message)}</textarea>
            </label>
            <p class="field-error" id="ann-error" role="alert"></p>
          </div>
          <div class="ann-preview-wrap"><span class="label">${esc(t("annPreview"))}</span>${annPreview()}</div>
        </div>
        ${annFoot()}
      </section>`;
  }

  function onAnnInput(target) {
    const d = state.annDraft;
    if (target.id === "ann-enabled") d.enabled = target.checked;
    else if (target.id === "ann-severity") d.severity = target.value;
    else if (target.id === "ann-title") d.title = target.value;
    else if (target.id === "ann-message") {
      d.message = target.value;
      $("#ann-count").textContent = `${d.message.length} / 1000`;
    } else return;
    $("#ann-error").textContent = "";
    $("#ann-preview").outerHTML = annPreview();
    $("#ann-foot").outerHTML = annFoot();
  }

  async function saveAnnouncement(republish = false) {
    const d = state.annDraft;
    if (d.enabled && !d.message.trim()) {
      $("#ann-error").textContent = t("annNeedMessage");
      $("#ann-message").focus();
      return;
    }
    const body = { enabled: d.enabled, severity: d.severity, title: d.title, message: d.message, republish };
    state.announcement = await api("PUT", "/api/admin/announcement", body);
    state.annDraft = { ...state.announcement };
    render();
    toast(t(republish ? "annRepublished" : "annSaved"), "success");
  }

  function onUiToggle(input) {
    const key = input.dataset.uiKey;
    const on = input.checked;
    state.uiDraft[key] = on;
    const row = input.closest(".ui-row");
    row.classList.toggle("is-off", !on);
    row.classList.toggle("is-changed", on !== (state.ui.visibility[key] !== false));
    const badge = $(".ui-state", row);
    badge.classList.toggle("badge-danger", !on);
    badge.innerHTML = `${icon(on ? "eye" : "eyeOff")}<span>${esc(t(on ? "uiShown" : "uiHidden"))}</span>`;
    $("#ui-foot").outerHTML = uiFoot();
  }

  async function saveUi() {
    state.ui = await api("PUT", "/api/admin/ui", { visibility: state.uiDraft });
    state.uiDraft = { ...state.ui.visibility };
    render();
    toast(t("uiSaved"), "success");
  }

  async function resetUi() {
    if (!(await confirmDialog(t("uiResetConfirm"), t("uiResetText"), t("ssoReset")))) return;
    state.ui = await api("POST", "/api/admin/ui/reset");
    state.uiDraft = { ...state.ui.visibility };
    render();
    toast(t("uiResetDone"), "success");
  }

  function updateSsoDot() {
    const ssoOn = Boolean(state.auth && state.auth.sections.keycloak.enabled);
    const ldapOn = Boolean(state.auth && state.auth.ldap_configured);
    $("#sso-dot").className = `sso-dot ${ssoOn || ldapOn ? "on" : ""}`;
    $("#sso-dot").title = `Keycloak: ${ssoOn ? t("ssoStatusOn") : t("ssoStatusOff")} · LDAP: ${ldapOn ? t("ssoStatusOn") : t("ssoStatusOff")}`;
  }

  // --------------------------------------------------------------- drawer

  function openDrawer(drawer) {
    state.drawer = drawer;
    renderDrawer();
    const el = $("#drawer");
    const backdrop = $("#drawer-backdrop");
    el.hidden = false;
    backdrop.hidden = false;
    document.body.classList.add("modal-open");
    requestAnimationFrame(() => { el.classList.add("show"); backdrop.classList.add("show"); });
    const first = $("input:not([type=hidden]), textarea, select", el);
    if (first) setTimeout(() => first.focus(), 60);
  }

  function closeDrawer() {
    const el = $("#drawer");
    if (el.hidden) return;
    el.classList.remove("show");
    $("#drawer-backdrop").classList.remove("show");
    document.body.classList.remove("modal-open");
    state.drawer = null;
    state.builder = null;
    setTimeout(() => { el.hidden = true; $("#drawer-backdrop").hidden = true; }, 180);
  }

  function renderDrawer() {
    const d = state.drawer;
    if (!d) return;
    const views = { app: appEditor, stack: stackEditor, platform: platformEditor };
    const { title, body, foot } = views[d.type](d);
    $("#drawer-title").innerHTML = title;
    $("#drawer-body").innerHTML = body;
    $("#drawer-foot").innerHTML = foot;
  }

  const field = (label, control, hint = "") => `<label class="field"><span>${esc(label)}</span>${control}${hint ? `<span class="hint">${esc(hint)}</span>` : ""}</label>`;

  function iconEditor({ url, name, source, kind, id, hasUpload, extra = "" }) {
    return `
      <div class="fieldset">
        <div class="fieldset-title">${esc(t("icon"))}</div>
        <div class="icon-editor">
          ${appIcon(url, name, "lg")}
          <div style="display:flex;flex-direction:column;gap:8px">
            <span class="source">${esc(t("iconSource", source))}</span>
            <div class="actions">
              ${id != null ? `<button class="btn btn-secondary btn-sm" type="button" data-action="upload-icon" data-kind="${kind}" data-id="${esc(id)}">${icon("upload")}<span>${esc(t("upload"))}</span></button>` : `<span class="hint subtle">${esc(t("uploadAfterSave"))}</span>`}
              ${hasUpload ? `<button class="btn btn-ghost btn-sm" type="button" data-action="remove-icon" data-kind="${kind}" data-id="${esc(id)}">${icon("trash")}<span>${esc(t("removeUpload"))}</span></button>` : ""}
              ${extra}
            </div>
          </div>
        </div>
      </div>`;
  }

  function appEditor(d) {
    const a = state.apps.find((x) => x.id === d.id);
    if (!a) return { title: "", body: "", foot: "" };
    const o = a.override || {};
    const srcLabels = { upload: t("srcUpload"), exe: t("srcExe"), msi: t("srcMsi"), folder: t("srcFolder"), builtin: t("srcBuiltin") };
    const catOptions = [`<option value="">${esc(t("auto"))}</option>`]
      .concat(state.options.categories.map((c) => `<option value="${esc(c.id)}" ${o.category === c.id ? "selected" : ""}>${esc(state.lang === "en" ? c.label_en : c.label_he)}</option>`)).join("");
    const featuredVal = o.featured === true ? "yes" : o.featured === false ? "no" : "";
    const files = a.files.map((f) => `
      <li class="file-toggle ${f.hidden ? "off" : ""}">
        <input type="checkbox" name="file" value="${esc(f.rel_path)}" ${f.hidden ? "" : "checked"} aria-label="${esc(f.filename)}">
        <span class="file-name" title="${esc(f.rel_path)}">${esc(f.filename)}</span>
        ${f.version ? `<span class="version-tag">v${esc(f.version)}</span>` : ""}
        <span class="os-tag">${esc(f.os)}</span>
        <span class="size-tag">${esc(f.size_human)}</span>
      </li>`).join("");
    return {
      title: `${esc(t("editApp"))} · ${bdi(a.scanned_name)}`,
      body: `
        <form class="form" id="drawer-form" novalidate>
          ${iconEditor({ url: a.icon_url, name: a.name, source: srcLabels[a.icon_source] || t("srcNone"), kind: "app", id: a.id, hasUpload: Boolean(o.icon_file) })}
          ${field(t("displayName"), `<input class="input" name="display_name" maxlength="120" value="${esc(o.display_name || "")}" placeholder="${esc(a.scanned_name)}">`)}
          <div class="form-row">
            ${field(t("category"), `<select class="select" name="category" style="width:100%">${catOptions}</select>`)}
            ${field(t("featured"), `<select class="select" name="featured" style="width:100%"><option value="">${esc(t("auto"))}</option><option value="yes" ${featuredVal === "yes" ? "selected" : ""}>${esc(t("featuredYes"))}</option><option value="no" ${featuredVal === "no" ? "selected" : ""}>${esc(t("featuredNo"))}</option></select>`)}
          </div>
          ${field(t("descriptionHe"), `<textarea class="textarea" name="description_he" maxlength="2000" dir="rtl" placeholder="${esc(a.scanned_description_he)}">${esc(o.description_he || "")}</textarea>`)}
          ${field(t("descriptionEn"), `<textarea class="textarea" name="description_en" maxlength="2000" dir="ltr" placeholder="${esc(a.scanned_description_en)}">${esc(o.description_en || "")}</textarea>`)}
          ${field(t("tags"), `<input class="input" name="tags" maxlength="400" value="${esc((o.tags || []).join(", "))}" placeholder="${esc((o.tags ? [] : a.tags).join(", "))}">`, t("tagsHint"))}
          <label class="check"><input type="checkbox" name="hidden" ${o.hidden ? "checked" : ""}>${esc(t("hideApp"))}</label>
          <div class="fieldset">
            <div class="fieldset-title"><span>${esc(t("installersVisibility"))}</span><span class="subtle mono">${a.files.length}</span></div>
            <p class="hint subtle" style="margin-bottom:10px;font-size:12px">${esc(t("installersHint"))}</p>
            <ul class="file-toggle-list">${files}</ul>
          </div>
          <div class="form-error" id="drawer-error" role="alert"></div>
        </form>`,
      foot: `
        ${a.override ? `<button class="btn btn-danger" type="button" data-action="reset-app" data-id="${esc(a.id)}">${esc(t("resetOverrides"))}</button>` : ""}
        <span class="spacer"></span>
        <button class="btn btn-ghost" type="button" data-action="close-drawer">${esc(t("cancel"))}</button>
        <button class="btn btn-primary" type="button" data-action="save-app" data-id="${esc(a.id)}">${esc(t("save"))}</button>`,
    };
  }

  function colorPicker(current) {
    return `<div class="swatches">${COLORS.map((c) => `<button type="button" class="swatch ${c.toLowerCase() === String(current).toLowerCase() ? "active" : ""}" style="--swatch:${c}" data-action="pick-color" data-color="${c}" aria-label="${c}"></button>`).join("")}<input type="color" class="color-input" name="color" value="${esc(current)}" aria-label="${esc(t("color"))}"></div>`;
  }

  function builderHtml() {
    const b = state.builder;
    const selected = b.apps;
    const selectedIds = new Set(selected.map((r) => r.appId).filter(Boolean));
    const term = state.builderSearch.trim().toLowerCase();
    const available = state.apps
      .filter((a) => !selectedIds.has(a.id))
      .filter((a) => !term || `${a.name} ${a.folder}`.toLowerCase().includes(term));
    const availableHtml = available.map((a) => `
      <li class="builder-item">${appIcon(a.icon_url, a.name, "xs")}<span class="name">${bdi(a.name)}</span>
        <button class="icon-btn icon-btn-sm" type="button" data-action="builder-add" data-id="${esc(a.id)}" title="${esc(t("add"))}" aria-label="${esc(t("add"))}">${icon("plus")}</button></li>`).join("");
    const selectedHtml = selected.map((r, i) => {
      const a = r.appId ? state.apps.find((x) => x.id === r.appId) : null;
      return `
        <li class="builder-item ${a ? "" : "missing"}">
          <span class="idx">${i + 1}</span>
          ${a ? appIcon(a.icon_url, a.name, "xs") : `<span class="app-icon app-icon-xs app-icon-letter">!</span>`}
          <span class="name" title="${esc(a ? a.folder : `${r.ref} - ${t("notInScan")}`)}">${bdi(a ? a.name : `${r.ref} (${t("notInScan")})`)}</span>
          <button class="icon-btn icon-btn-sm" type="button" data-action="builder-move" data-index="${i}" data-dir="-1" ${i === 0 ? "disabled" : ""} title="${esc(t("moveUp"))}" aria-label="${esc(t("moveUp"))}">${icon("up")}</button>
          <button class="icon-btn icon-btn-sm" type="button" data-action="builder-move" data-index="${i}" data-dir="1" ${i === selected.length - 1 ? "disabled" : ""} title="${esc(t("moveDown"))}" aria-label="${esc(t("moveDown"))}">${icon("down")}</button>
          <button class="icon-btn icon-btn-sm" type="button" data-action="builder-remove" data-index="${i}" title="${esc(t("remove"))}" aria-label="${esc(t("remove"))}">${icon("x")}</button>
        </li>`;
    }).join("");
    return `
      <div class="fieldset-title"><span>${esc(t("stackTools", selected.length))}</span></div>
      <div class="builder">
        <div class="builder-col">
          <span class="field-label">${esc(t("availableApps"))}</span>
          <label class="search" style="width:100%">${icon("search")}<input type="search" id="builder-search" autocomplete="off" placeholder="${esc(t("searchAvailable"))}" value="${esc(state.builderSearch)}"></label>
          <ul class="builder-list">${availableHtml || `<li class="builder-empty">—</li>`}</ul>
        </div>
        <div class="builder-col">
          <span class="field-label">${esc(t("selectedApps"))}</span>
          <ul class="builder-list" style="height:338px">${selectedHtml || `<li class="builder-empty">${esc(t("builderEmpty"))}</li>`}</ul>
        </div>
      </div>`;
  }

  function stackEditor(d) {
    const s = d.id ? state.stacks.find((x) => x.id === d.id) : null;
    if (!state.builder) {
      state.builder = {
        icon: s ? s.icon : "code",
        color: s ? s.color : COLORS[0],
        apps: (s ? s.apps : []).map((ref) => {
          const a = resolveRef(ref);
          return { ref, appId: a ? a.id : null };
        }),
      };
      state.builderSearch = "";
    }
    const b = state.builder;
    const glyphs = state.options.stack_glyphs.map((g) => `<button type="button" class="glyph-option ${b.icon === g ? "active" : ""}" data-action="pick-glyph" data-glyph="${esc(g)}" title="${esc(g)}" aria-label="${esc(g)}">${icon(g)}</button>`).join("");
    return {
      title: esc(s ? `${t("editStack")} · ${loc(s, "name")}` : t("newStack")),
      body: `
        <form class="form" id="drawer-form" novalidate>
          <div class="form-row">
            ${field(t("nameHe"), `<input class="input" name="name_he" maxlength="80" dir="rtl" required value="${esc(s ? s.name_he : "")}">`)}
            ${field(t("nameEn"), `<input class="input" name="name_en" maxlength="80" dir="ltr" required value="${esc(s ? s.name_en : "")}">`)}
          </div>
          <div class="form-row">
            ${field(t("descriptionHe"), `<textarea class="textarea" name="description_he" maxlength="300" dir="rtl">${esc(s ? s.description_he : "")}</textarea>`)}
            ${field(t("descriptionEn"), `<textarea class="textarea" name="description_en" maxlength="300" dir="ltr">${esc(s ? s.description_en : "")}</textarea>`)}
          </div>
          <div class="form-row">
            ${field(t("stackId"), `<input class="input mono" name="id" maxlength="64" dir="ltr" value="${esc(s ? s.id : "")}" ${s ? "disabled" : ""} pattern="[a-z0-9][a-z0-9-]*">`, s ? "" : t("stackIdHint"))}
            ${field(t("sortOrder"), positionInput(s ? s.sort_order : null, state.stacks.length), t("sortOrderHint"))}
          </div>
          <div class="field"><span class="field-label">${esc(t("glyph"))}</span><div class="glyph-picker">${glyphs}</div></div>
          <div class="field"><span class="field-label">${esc(t("color"))}</span>${colorPicker(b.color)}</div>
          <div class="fieldset" id="builder">${builderHtml()}</div>
          <div class="form-error" id="drawer-error" role="alert"></div>
        </form>`,
      foot: `
        ${s ? `<button class="btn btn-danger" type="button" data-action="delete-stack" data-id="${esc(s.id)}">${esc(t("delete"))}</button>` : ""}
        <span class="spacer"></span>
        <button class="btn btn-ghost" type="button" data-action="close-drawer">${esc(t("cancel"))}</button>
        <button class="btn btn-primary" type="button" data-action="save-stack" data-id="${esc(s ? s.id : "")}">${esc(t("save"))}</button>`,
    };
  }

  // Existing items can move within 1..N; a new item can also take slot N+1 (the end).
  function positionInput(current, count) {
    const max = current == null ? count + 1 : Math.max(count, 1);
    const value = current == null ? max : current;
    return `<input class="input mono" name="sort_order" type="number" min="1" max="${max}" step="1" value="${esc(value)}">`;
  }

  function readPosition(form) {
    const value = Number(form.sort_order.value);
    const max = Number(form.sort_order.max);
    return Number.isInteger(value) && value >= 1 ? Math.min(value, max) : null;
  }

  function platformEditor(d) {
    const p = d.id != null ? state.platforms.find((x) => x.id === d.id) : null;
    if (!state.builder) state.builder = { icon: p ? p.icon : "globe", color: p ? p.color : COLORS[0] };
    const b = state.builder;
    const builtins = ["globe", ...state.options.builtin_icons].map((name) => `
      <button type="button" class="glyph-option ${b.icon === name ? "active" : ""}" data-action="pick-glyph" data-glyph="${esc(name)}" title="${esc(name)}" aria-label="${esc(name)}">
        ${name === "globe" ? icon("globe") : `<img src="/static/icons/${esc(name)}.svg" alt="" loading="lazy">`}
      </button>`).join("");
    const fetchBtn = p ? `<button class="btn btn-ghost btn-sm" type="button" data-action="fetch-favicon" data-id="${p.id}">${icon("globe")}<span>${esc(t("fetchFavicon"))}</span></button>` : "";
    return {
      title: esc(p ? `${t("editPlatform")} · ${p.name}` : t("newPlatform")),
      body: `
        <form class="form" id="drawer-form" novalidate>
          ${iconEditor({ url: p ? p.icon_url : null, name: p ? p.name : "?", source: p ? platformSource(p) : t("srcNone"), kind: "platform", id: p ? p.id : null, hasUpload: Boolean(p && p.icon_file), extra: fetchBtn })}
          <div class="form-row">
            ${field(t("name"), `<input class="input" name="name" maxlength="80" required value="${esc(p ? p.name : "")}">`)}
            ${field(t("url"), `<input class="input mono" name="url" maxlength="500" dir="ltr" required placeholder="https://service.example.com" value="${esc(p ? p.url : "")}">`)}
          </div>
          <div class="form-row">
            ${field(t("descriptionHe"), `<textarea class="textarea" name="description_he" maxlength="300" dir="rtl">${esc(p ? p.description_he : "")}</textarea>`)}
            ${field(t("descriptionEn"), `<textarea class="textarea" name="description_en" maxlength="300" dir="ltr">${esc(p ? p.description_en : "")}</textarea>`)}
          </div>
          <div class="field"><span class="field-label">${esc(t("builtinIcon"))}</span><div class="glyph-picker">${builtins}</div></div>
          <div class="form-row">
            <div class="field"><span class="field-label">${esc(t("color"))}</span>${colorPicker(b.color)}</div>
            ${field(t("sortOrder"), positionInput(p ? p.sort_order : null, state.platforms.length), t("sortOrderHint"))}
          </div>
          <div class="form-error" id="drawer-error" role="alert"></div>
        </form>`,
      foot: `
        ${p ? `<button class="btn btn-danger" type="button" data-action="delete-platform" data-id="${p.id}">${esc(t("delete"))}</button>` : ""}
        <span class="spacer"></span>
        <button class="btn btn-ghost" type="button" data-action="close-drawer">${esc(t("cancel"))}</button>
        <button class="btn btn-primary" type="button" data-action="save-platform" data-id="${p ? p.id : ""}">${esc(t("save"))}</button>`,
    };
  }

  function rerenderBuilder() {
    const host = $("#builder");
    if (!host) return;
    const focused = document.activeElement && document.activeElement.id === "builder-search";
    host.innerHTML = builderHtml();
    if (focused) {
      const input = $("#builder-search");
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
  }

  function drawerError(message) {
    const el = $("#drawer-error");
    if (el) el.textContent = message || "";
  }

  // --------------------------------------------------------------- saving

  async function saveApp(id) {
    const form = $("#drawer-form");
    const tagsRaw = form.tags.value.trim();
    const featured = form.featured.value;
    const body = {
      display_name: form.display_name.value.trim() || null,
      description_he: form.description_he.value.trim() || null,
      description_en: form.description_en.value.trim() || null,
      category: form.category.value || null,
      tags: tagsRaw ? tagsRaw.split(",").map((s) => s.trim()).filter(Boolean) : null,
      featured: featured === "yes" ? true : featured === "no" ? false : null,
      hidden: form.hidden.checked,
      hidden_files: $$("input[name=file]", form).filter((c) => !c.checked).map((c) => c.value),
    };
    const updated = await api("PUT", `/api/admin/apps/${encodeURIComponent(id)}`, body);
    replaceApp(updated);
    toast(t("saved"), "success");
    closeDrawer();
    reload("overview").catch(fail);
  }

  function replaceApp(updated) {
    const i = state.apps.findIndex((a) => a.id === updated.id);
    if (i >= 0) state.apps[i] = updated;
    render();
  }

  async function saveStack(id) {
    const form = $("#drawer-form");
    const b = state.builder;
    const body = {
      name_he: form.name_he.value,
      name_en: form.name_en.value,
      description_he: form.description_he.value,
      description_en: form.description_en.value,
      icon: b.icon,
      color: b.color,
      sort_order: readPosition(form),
      apps: b.apps.map((r) => r.appId || r.ref),
    };
    if (!id) body.id = form.id.value.trim() || null;
    if (id) await api("PUT", `/api/admin/stacks/${encodeURIComponent(id)}`, body);
    else await api("POST", "/api/admin/stacks", body);
    toast(t("saved"), "success");
    closeDrawer();
    await reload("stacks", "overview");
  }

  async function savePlatform(id) {
    const form = $("#drawer-form");
    const b = state.builder;
    const body = {
      name: form.name.value,
      url: form.url.value.trim(),
      description_he: form.description_he.value,
      description_en: form.description_en.value,
      icon: b.icon,
      color: b.color,
      sort_order: readPosition(form),
    };
    const saved = id
      ? await api("PUT", `/api/admin/platforms/${id}`, body)
      : await api("POST", "/api/admin/platforms", body);
    toast(t("saved"), "success");
    await reload("platforms", "overview");
    if (!id) {
      state.builder = null;
      openDrawer({ type: "platform", id: saved.id });
    } else {
      closeDrawer();
    }
  }

  function confirmDialog(title, text, okLabel) {
    return new Promise((resolve) => {
      const el = $("#confirm");
      $("#confirm-title").textContent = title;
      $("#confirm-text").textContent = text;
      $("#confirm-ok").textContent = okLabel;
      el.hidden = false;
      requestAnimationFrame(() => el.classList.add("show"));
      const done = (value) => {
        el.classList.remove("show");
        setTimeout(() => { el.hidden = true; }, 150);
        $("#confirm-ok").onclick = null;
        $("#confirm-cancel").onclick = null;
        resolve(value);
      };
      $("#confirm-ok").onclick = () => done(true);
      $("#confirm-cancel").onclick = () => done(false);
      $("#confirm-ok").focus();
    });
  }

  // ---------------------------------------------------------------- icons

  function readAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
  }

  async function onIconFile(event) {
    const input = event.target;
    const file = input.files && input.files[0];
    const target = state.uploadTarget;
    input.value = "";
    if (!file || !target) return;
    if (file.size > MAX_ICON_BYTES) {
      toast(t("iconTooLarge"), "error");
      return;
    }
    try {
      const data = await readAsDataUrl(file);
      if (target.kind === "app") {
        replaceApp(await api("POST", `/api/admin/apps/${encodeURIComponent(target.id)}/icon`, { data_base64: data }));
      } else {
        await api("POST", `/api/admin/platforms/${target.id}/icon`, { data_base64: data });
        await reload("platforms");
      }
      toast(t("iconUploaded"), "success");
      if (state.drawer) renderDrawer();
    } catch (err) {
      fail(err);
    }
  }

  async function removeIcon(kind, id) {
    if (kind === "app") replaceApp(await api("DELETE", `/api/admin/apps/${encodeURIComponent(id)}/icon`));
    else {
      await api("DELETE", `/api/admin/platforms/${id}/icon`);
      await reload("platforms");
    }
    toast(t("iconRemoved"), "success");
    if (state.drawer) renderDrawer();
  }

  // ------------------------------------------------------------- rescans

  let pollTimer = null;

  function pollScan() {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(async () => {
      try {
        const status = await fetch("/api/status", { cache: "no-store" }).then((r) => r.json());
        if (status.scanning) {
          pollScan();
          return;
        }
        state.scanning = false;
        await reload("overview", "apps");
        if (status.error) toast(`${t("rescanFailed")}: ${status.error}`, "error", 6000);
        else toast(t("rescanDone", status.apps, status.files), "success");
      } catch (_) {
        pollScan();
      }
    }, 1500);
  }

  async function rescan() {
    const result = await api("POST", "/api/admin/rescan", { invalidate: true });
    state.scanning = true;
    render();
    toast(result.status === "already_running" ? t("rescanRunning") : t("rescanStarted"), "info");
    pollScan();
  }

  async function saveSchedule() {
    const input = $("#rescan-minutes");
    const minutes = Number(input && input.value);
    if (!Number.isInteger(minutes) || minutes < 0 || minutes > 10080) {
      toast(t("scheduleInvalid"), "error");
      return;
    }
    const result = await api("PUT", "/api/admin/settings", { auto_rescan_minutes: minutes });
    state.overview.config.auto_rescan_minutes = result.auto_rescan_minutes;
    render();
    toast(result.auto_rescan_minutes > 0 ? t("scheduleSaved", result.auto_rescan_minutes) : t("scheduleOff"), "success");
  }

  async function refreshFavicons() {
    let fetched = 0;
    for (const p of state.platforms) {
      try {
        const res = await api("POST", `/api/admin/platforms/${p.id}/favicon`);
        if (res.fetched) fetched += 1;
      } catch (err) {
        if (err.status === 401) return;
      }
    }
    await reload("platforms");
    toast(t("faviconsDone", fetched, state.platforms.length), fetched ? "success" : "info");
  }

  // --------------------------------------------------------------- events

  async function handleAction(el, event) {
    const { action, id } = el.dataset;
    try {
      switch (action) {
        case "close-drawer": closeDrawer(); break;
        case "rescan": await rescan(); break;
        case "save-schedule": el.disabled = true; try { await saveSchedule(); } finally { el.disabled = false; } break;
        case "schedule-preset": { const input = $("#rescan-minutes"); if (input) input.value = el.dataset.minutes; break; }
        case "refresh-favicons": el.disabled = true; await refreshFavicons(); el.disabled = false; break;
        case "app-filter": state.appFilter = el.dataset.filter; render(); break;
        case "edit-app": event.stopPropagation(); state.builder = null; openDrawer({ type: "app", id }); break;
        case "save-app": el.disabled = true; drawerError(""); await saveApp(id); break;
        case "reset-app":
          if (await confirmDialog(t("confirmReset"), t("confirmResetText"), t("resetOverrides"))) {
            replaceApp(await api("DELETE", `/api/admin/apps/${encodeURIComponent(id)}`));
            toast(t("resetDone"), "success");
            renderDrawer();
            reload("overview").catch(fail);
          }
          break;
        case "new-stack": state.builder = null; openDrawer({ type: "stack", id: null }); break;
        case "edit-stack": state.builder = null; openDrawer({ type: "stack", id }); break;
        case "save-stack": el.disabled = true; drawerError(""); await saveStack(id); break;
        case "delete-stack":
          event.stopPropagation();
          if (await confirmDialog(t("confirmDeleteStack"), t("confirmDeleteText"), t("delete"))) {
            await api("DELETE", `/api/admin/stacks/${encodeURIComponent(id)}`);
            closeDrawer();
            toast(t("deleted"), "success");
            await reload("stacks", "overview");
          }
          break;
        case "new-platform": state.builder = null; openDrawer({ type: "platform", id: null }); break;
        case "edit-platform": event.stopPropagation(); state.builder = null; openDrawer({ type: "platform", id: Number(id) }); break;
        case "save-platform": el.disabled = true; drawerError(""); await savePlatform(id ? Number(id) : null); break;
        case "delete-platform":
          event.stopPropagation();
          if (await confirmDialog(t("confirmDeletePlatform"), t("confirmDeleteText"), t("delete"))) {
            await api("DELETE", `/api/admin/platforms/${id}`);
            closeDrawer();
            toast(t("deleted"), "success");
            await reload("platforms", "overview");
          }
          break;
        case "fetch-favicon": {
          el.disabled = true;
          const res = await api("POST", `/api/admin/platforms/${id}/favicon`);
          await reload("platforms");
          toast(res.fetched ? t("faviconFetched") : t("faviconMissing"), res.fetched ? "success" : "info");
          renderDrawer();
          break;
        }
        case "upload-icon":
          state.uploadTarget = { kind: el.dataset.kind, id: el.dataset.kind === "platform" ? Number(id) : id };
          $("#icon-file").click();
          break;
        case "remove-icon": await removeIcon(el.dataset.kind, el.dataset.kind === "platform" ? Number(id) : id); break;
        case "pick-glyph":
          state.builder.icon = el.dataset.glyph;
          $$(".glyph-option").forEach((g) => g.classList.toggle("active", g === el));
          break;
        case "pick-color":
          state.builder.color = el.dataset.color;
          $$(".swatch").forEach((s) => s.classList.toggle("active", s === el));
          $("input[name=color]").value = el.dataset.color;
          break;
        case "builder-add": {
          state.builder.apps.push({ ref: id, appId: id });
          rerenderBuilder();
          break;
        }
        case "builder-remove": state.builder.apps.splice(Number(el.dataset.index), 1); rerenderBuilder(); break;
        case "builder-move": {
          const i = Number(el.dataset.index);
          const j = i + Number(el.dataset.dir);
          const list = state.builder.apps;
          if (j >= 0 && j < list.length) [list[i], list[j]] = [list[j], list[i]];
          rerenderBuilder();
          break;
        }
        case "fb-status-filter": state.fbStatus = el.dataset.status; render(); break;
        case "fb-expand": {
          const fid = Number(id);
          if (state.fbExpanded.has(fid)) state.fbExpanded.delete(fid);
          else state.fbExpanded.add(fid);
          render();
          break;
        }
        case "delete-feedback":
          if (await confirmDialog(t("confirmDeleteFeedback"), t("confirmDeleteText"), t("delete"))) {
            await api("DELETE", `/api/admin/feedback/${Number(id)}`);
            toast(t("deleted"), "success");
            await reload("feedback", "overview");
          }
          break;
        case "auth-save": await saveAuthSection(el.dataset.section, el); break;
        case "auth-reset": await resetAuthSection(el.dataset.section); break;
        case "auth-test": await runAuthTest(el.dataset.kind, el); break;
        case "ui-save": el.disabled = true; try { await saveUi(); } finally { el.disabled = false; } break;
        case "ui-reset": await resetUi(); break;
        case "ann-save":
        case "ann-republish":
          el.disabled = true;
          try { await saveAnnouncement(action === "ann-republish"); } finally { el.disabled = false; }
          break;
        case "ui-show-all":
          Object.keys(state.uiDraft).forEach((k) => { state.uiDraft[k] = true; });
          render();
          break;
        default: break;
      }
    } catch (err) {
      if (["save-app", "save-stack", "save-platform"].includes(action)) {
        drawerError(err.message);
        el.disabled = false;
      }
      fail(err);
    }
  }

  function applyLanguage(lang) {
    state.lang = lang === "en" ? "en" : "he";
    window.PAKAL.saveLang(state.lang);
    window.PAKAL.applyDocumentLang(state.lang);
    document.title = `${t("brand")} · ${t("adminBadge")}`;
    $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    $$("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); el.setAttribute("aria-label", t(el.dataset.i18nTitle)); });
    $$(".segmented [data-lang]").forEach((b) => b.classList.toggle("active", b.dataset.lang === state.lang));
    if (state.session) render();
    if (state.drawer) renderDrawer();
  }

  function bindEvents() {
    document.addEventListener("click", (event) => {
      const el = event.target.closest("[data-action]");
      if (el && !el.disabled) handleAction(el, event);
    });
    $("#login-form").addEventListener("submit", onLogin);
    $("#login-sso").addEventListener("click", async (event) => {
      event.preventDefault();
      try { sessionStorage.removeItem(NO_AUTO_SSO); } catch (_) { /* storage disabled */ }
      const me = await fetch("/api/auth/me", { cache: "no-store", credentials: "same-origin" }).then((r) => r.json()).catch(() => null);
      if (me && me.authenticated) {
        const session = await trySsoSession();
        if (session) await showShell(session);
        return;
      }
      window.location.href = `/api/auth/sso/login?next=${encodeURIComponent(viewPath(state.view))}`;
    });
    $("#logout-btn").addEventListener("click", logout);
    $("#icon-file").addEventListener("change", onIconFile);
    $("#drawer-backdrop").addEventListener("click", closeDrawer);
    $$(".side-item").forEach((b) => b.addEventListener("click", () => {
      state.view = VIEWS.includes(b.dataset.view) ? b.dataset.view : "overview";
      history.replaceState(null, "", viewPath(state.view));
      render();
    }));
    document.addEventListener("change", (event) => {
      const target = event.target;
      if (target.matches("[data-feedback-status]")) updateFeedbackStatus(target);
      else if (target.matches("[data-ui-key]")) onUiToggle(target);
      else if (target.id === "ann-enabled" || target.id === "ann-severity") onAnnInput(target);
      else if (target.id === "fb-category-filter") {
        state.fbCategory = target.value;
        render();
      }
    });
    $$(".segmented [data-lang]").forEach((b) => b.addEventListener("click", () => applyLanguage(b.dataset.lang)));

    const onAppSearch = debounce((value) => {
      state.appSearch = value;
      const tbody = $("#apps-tbody");
      if (tbody) tbody.innerHTML = appRows();
    }, 100);
    const onBuilderSearch = debounce((value) => {
      state.builderSearch = value;
      rerenderBuilder();
    }, 100);
    document.addEventListener("input", (event) => {
      const target = event.target;
      const authField = target.closest && target.closest(".auth-field.has-error");
      if (authField) {
        authField.classList.remove("has-error");
        const errEl = authField.querySelector(".field-error");
        if (errEl) errEl.textContent = "";
      }
      if (target.id === "ann-title" || target.id === "ann-message") onAnnInput(target);
      else if (target.id === "app-search") onAppSearch(target.value);
      else if (target.id === "builder-search") onBuilderSearch(target.value);
      else if (target.name === "color" && state.builder) {
        state.builder.color = target.value.toUpperCase();
        $$(".swatch").forEach((s) => s.classList.toggle("active", s.dataset.color.toLowerCase() === target.value.toLowerCase()));
      } else if (target.name === "file") {
        target.closest(".file-toggle").classList.toggle("off", !target.checked);
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && event.target.id === "lookup-username") {
        event.preventDefault();
        const b = $('[data-action="auth-test"][data-kind="lookup"]');
        if (b && !b.disabled) b.click();
        return;
      }
      if (event.target.closest && event.target.closest(".auth-card") && event.key === "Enter" && event.target.tagName === "INPUT") {
        event.preventDefault();
        return;
      }
      if (event.key !== "Escape") return;
      if (!$("#confirm").hidden) $("#confirm-cancel").click();
      else if (state.drawer) closeDrawer();
    });
  }

  async function init() {
    window.PAKAL.hydrateIcons();
    $$("[data-admin-home]").forEach((a) => { a.href = ADMIN_BASE; });
    $("#login-sso").href = `/api/auth/sso/login?next=${encodeURIComponent(ADMIN_BASE)}`;
    const fromPath = window.location.pathname.split("/")[2] || "";
    const fromHash = window.location.hash.slice(1);
    if (VIEWS.includes(fromPath)) state.view = fromPath;
    else if (fromPath === "ldap" || fromPath === "auth") state.view = "sso";
    else if (VIEWS.includes(fromHash)) state.view = fromHash;
    bindEvents();
    applyLanguage(state.lang);
    try {
      const meta = await fetch("/api/admin/meta", { cache: "no-store" }).then((r) => r.json());
      const res = await fetch("/api/admin/session", { cache: "no-store", credentials: "same-origin" });
      $("#login-sso").hidden = !meta.sso;
      $("#login-divider").hidden = !meta.sso;
      if (res.ok) { await showShell(await res.json()); return; }
      let noAuto = false;
      try { noAuto = sessionStorage.getItem(NO_AUTO_SSO) === "1"; } catch (_) { /* storage disabled */ }
      const me = await fetch("/api/auth/me", { cache: "no-store", credentials: "same-origin" }).then((r) => r.json()).catch(() => null);
      showLogin(meta.configured ? "" : t("notConfigured"));
      if (me && me.authenticated && me.user && me.user.admin && !noAuto) {
        const session = await trySsoSession();
        if (session) { await showShell(session); return; }
      } else if (me && me.authenticated && me.user && !me.user.admin) {
        $("#login-error").textContent = t("ssoNoAdmin");
      }
    } catch (_) {
      showLogin(t("requestFailed"));
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
