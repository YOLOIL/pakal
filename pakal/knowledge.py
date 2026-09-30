"""Static knowledge base: categories, well-known applications and first-run defaults."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

CATEGORIES: List[Tuple[str, str, str]] = [
    ("all", "הכל", "All"),
    ("code", "פיתוח", "Development"),
    ("text", "עורכים ומסמכים", "Editors & Docs"),
    ("database", "מסדי נתונים ודאטה", "Data & Databases"),
    ("design", "עיצוב ומדיה", "Design & Media"),
    ("tools", "כלים ותשתית", "Tools & Infra"),
]
CATEGORY_IDS = {cid for cid, _, _ in CATEGORIES if cid != "all"}
CATEGORY_ALIASES: Dict[str, str] = {
    "קוד": "code", "פיתוח": "code", "dev": "code", "development": "code", "ide": "code",
    "programming": "code", "טקסט": "text", "editor": "text", "editors": "text", "office": "text",
    "documents": "text", "מסד נתונים": "database", "מסדי נתונים": "database", "db": "database",
    "databases": "database", "data": "database", "sql": "database", "עיצוב": "design",
    "graphics": "design", "media": "design", "כלים": "tools", "tool": "tools",
    "utilities": "tools", "utility": "tools", "network": "tools", "browser": "tools",
}

# key: (category, description_he, description_en, tags, aliases)
KNOWN_APPS: Dict[str, Tuple[str, str, str, List[str], List[str]]] = {
    "vscode": ("code", "עורך קוד קל ומהיר של מיקרוסופט עם תמיכה בהרחבות, דיבאג ו-Git מובנה.",
               "Lightweight code editor by Microsoft with extensions, debugging and built-in Git.",
               ["IDE", "Editor"], ["visualstudiocode", "vscodeusersetup", "vscodesetup"]),
    "visualstudio": ("code", "סביבת פיתוח מלאה של מיקרוסופט לפיתוח ב-.NET, C++ ו-C#.",
                     "Full Microsoft IDE for .NET, C++ and C# development.", ["IDE", ".NET", "C++"],
                     ["vs2022", "vs2019", "visualstudiocommunity", "visualstudioprofessional", "vscommunity"]),
    "intellij": ("code", "סביבת פיתוח מתקדמת של JetBrains ל-Java, Kotlin ושפות JVM.",
                 "JetBrains IDE for Java, Kotlin and JVM languages.", ["IDE", "Java", "Kotlin"],
                 ["intellijidea", "idea", "ideaic", "ideaiu"]),
    "pycharm": ("code", "סביבת פיתוח ייעודית לפייתון של JetBrains עם השלמה חכמה ודיבאגר.",
                "JetBrains Python IDE with smart completion and debugger.", ["IDE", "Python"], []),
    "eclipse": ("code", "סביבת פיתוח קוד פתוח לפיתוח Java ושפות נוספות.",
                "Open-source IDE for Java and other languages.", ["IDE", "Java"], []),
    "androidstudio": ("code", "סביבת הפיתוח הרשמית לאפליקציות אנדרואיד.",
                      "Official IDE for Android application development.", ["IDE", "Android"], []),
    "git": ("code", "מערכת ניהול גרסאות מבוזרת.", "Distributed version control system.", ["VCS", "CLI"],
            ["gitforwindows", "gitscm"]),
    "python": ("code", "שפת תכנות לאוטומציה, דאטה, AI ופיתוח צד שרת.",
               "Language for automation, data, AI and backend development.", ["Runtime", "Language"],
               ["python3", "cpython"]),
    "nodejs": ("code", "סביבת הרצה ל-JavaScript בצד השרת, כוללת npm.",
               "Server-side JavaScript runtime, includes npm.", ["Runtime", "JavaScript"], ["node", "nodejslts"]),
    "java": ("code", "ערכת פיתוח וסביבת הרצה ל-Java (JDK).", "Java Development Kit and runtime.",
             ["Runtime", "JDK"], ["jdk", "openjdk", "jre", "temurin", "adoptium", "corretto"]),
    "golang": ("code", "שפת Go - קומפיילר וכלי פיתוח.", "Go programming language toolchain.",
               ["Language", "Compiler"], ["go"]),
    "dotnet": ("code", "ערכת פיתוח .NET SDK ו-Runtime של מיקרוסופט.", "Microsoft .NET SDK and runtime.",
               ["Runtime", ".NET"], ["dotnetsdk", "dotnetcore", "netframework", "dotnetruntime"]),
    "postman": ("code", "כלי לבדיקה, תיעוד ופיתוח של ממשקי API.", "API development, testing and documentation.",
                ["API", "REST"], []),
    "docker": ("tools", "פלטפורמת קונטיינרים לפיתוח והרצה של אפליקציות.",
               "Container platform for building and running applications.", ["Containers", "DevOps"],
               ["dockerdesktop", "dockerdesktopinstaller"]),
    "wsl": ("tools", "Windows Subsystem for Linux - הרצת לינוקס ישירות ב-Windows.",
            "Windows Subsystem for Linux.", ["Linux", "DevOps"], ["windowssubsystemforlinux", "wsl2"]),
    "terraform": ("tools", "תשתית כקוד (IaC) לניהול משאבי תשתית.", "Infrastructure as Code tooling.",
                  ["IaC", "DevOps"], []),
    "kubectl": ("tools", "כלי שורת פקודה לניהול אשכולות Kubernetes.", "Kubernetes command-line tool.",
                ["Kubernetes", "CLI"], ["kubernetes", "k8s"]),
    "helm": ("tools", "מנהל חבילות ל-Kubernetes.", "The package manager for Kubernetes.", ["Kubernetes"], []),
    "lens": ("tools", "ממשק גרפי לניהול וניטור אשכולות Kubernetes.",
             "Desktop GUI for managing Kubernetes clusters.", ["Kubernetes", "GUI"], ["openlens"]),
    "ansible": ("tools", "כלי אוטומציה לניהול תצורה ופריסה.", "Configuration management and deployment automation.",
                ["Automation", "DevOps"], []),
    "putty": ("tools", "לקוח SSH ו-Telnet קל משקל ל-Windows.", "Lightweight SSH and Telnet client.", ["SSH"], []),
    "winscp": ("tools", "לקוח SFTP/SCP/FTP להעברת קבצים מאובטחת.", "SFTP/SCP/FTP client for secure file transfer.",
               ["SFTP"], []),
    "mobaxterm": ("tools", "טרמינל מתקדם עם SSH, X11 וכלי רשת מובנים.",
                  "Enhanced terminal with SSH, X11 server and network tools.", ["SSH", "Terminal"], []),
    "filezilla": ("tools", "לקוח FTP/SFTP קוד פתוח להעברת קבצים.", "Open-source FTP/SFTP client.", ["FTP"], []),
    "7zip": ("tools", "תוכנת דחיסה וחילוץ קבצים בעלת יחס דחיסה גבוה.", "File archiver with a high compression ratio.",
             ["Archive"], ["7z", "sevenzip"]),
    "winrar": ("tools", "תוכנת דחיסה וחילוץ לארכיוני RAR ו-ZIP.", "Archive manager for RAR and ZIP files.",
               ["Archive"], []),
    "chrome": ("tools", "דפדפן האינטרנט של Google.", "Google's web browser.", ["Browser"],
               ["googlechrome", "chromesetup", "chromestandaloneenterprise"]),
    "firefox": ("tools", "דפדפן קוד פתוח של Mozilla.", "Mozilla's open-source browser.", ["Browser"],
                ["mozillafirefox"]),
    "edge": ("tools", "דפדפן Microsoft Edge מבוסס Chromium.", "Chromium-based Microsoft Edge browser.",
             ["Browser"], ["microsoftedge", "msedge"]),
    "wireshark": ("tools", "מנתח תעבורת רשת לניטור ואבחון תקלות.", "Network protocol analyzer.",
                  ["Network", "Monitoring"], []),
    "vlc": ("design", "נגן מדיה קוד פתוח התומך כמעט בכל פורמט.", "Open-source media player.", ["Media"],
            ["vlcmediaplayer"]),
    "obs": ("design", "תוכנה להקלטת מסך ושידור.", "Screen recording and streaming software.", ["Recording"],
            ["obsstudio"]),
    "jmeter": ("tools", "כלי לבדיקות עומסים וביצועים.", "Load and performance testing tool.", ["Testing", "Load"],
               ["apachejmeter"]),
    "selenium": ("tools", "תשתית לאוטומציית בדיקות דפדפן.", "Browser automation framework for testing.",
                 ["Testing", "Automation"], ["seleniumide", "seleniumserver", "chromedriver"]),
    "soapui": ("tools", "כלי לבדיקות פונקציונליות של שירותי SOAP ו-REST.", "Functional testing for SOAP and REST APIs.",
               ["Testing", "API"], []),
    "notepadplusplus": ("text", "עורך טקסט וקוד קל ומהיר ל-Windows.", "Fast, lightweight text and code editor.",
                        ["Editor"], ["notepadpp", "npp", "notepad"]),
    "sublimetext": ("text", "עורך טקסט מהיר ומתקדם למפתחים.", "Sophisticated text editor for code and prose.",
                    ["Editor"], ["sublime"]),
    "vim": ("text", "עורך טקסט מבוסס מקלדת לשורת הפקודה.", "Keyboard-driven text editor.", ["Editor", "CLI"],
            ["gvim", "neovim", "nvim"]),
    "libreoffice": ("text", "חבילת אופיס חינמית: מסמכים, גיליונות ומצגות.",
                    "Office suite: documents, spreadsheets and presentations.", ["Office"], []),
    "adobereader": ("text", "קורא קבצי PDF של Adobe.", "Adobe's PDF reader.", ["PDF"],
                    ["acrobatreader", "acrobat", "adobeacrobat", "readerdc"]),
    "obsidian": ("text", "עורך הערות מבוסס Markdown לניהול ידע.", "Markdown-based knowledge base and notes.",
                 ["Markdown"], []),
    "dbeaver": ("database", "כלי ניהול מסדי נתונים אוניברסלי.", "Universal database client for SQL engines.",
                ["SQL", "Client"], []),
    "ssms": ("database", "SQL Server Management Studio.", "SQL Server Management Studio.", ["SQL Server"],
             ["sqlservermanagementstudio", "managementstudio"]),
    "sqlserver": ("database", "מנוע מסד הנתונים Microsoft SQL Server.", "Microsoft SQL Server database engine.",
                  ["SQL Server"], ["mssql", "sqlexpress", "sqlserverexpress"]),
    "mysqlworkbench": ("database", "כלי עיצוב וניהול עבור MySQL.", "Design and administration tool for MySQL.",
                       ["MySQL"], ["mysql"]),
    "pgadmin": ("database", "ממשק ניהול גרפי ל-PostgreSQL.", "Administration GUI for PostgreSQL.", ["PostgreSQL"],
                ["pgadmin4", "postgresql", "postgres"]),
    "mongodbcompass": ("database", "ממשק גרפי לעבודה עם MongoDB.", "GUI for exploring and querying MongoDB.",
                       ["MongoDB", "NoSQL"], ["mongodb", "mongo", "compass"]),
    "redis": ("database", "מסד נתונים In-Memory מסוג Key-Value.", "In-memory key-value data store.",
              ["Redis", "Cache"], ["redisinsight"]),
    "anaconda": ("database", "הפצת פייתון למדעי הנתונים כולל Conda.", "Python distribution for data science.",
                 ["Data Science", "Python"], ["miniconda", "conda"]),
    "jupyter": ("database", "מחברות אינטראקטיביות לניתוח נתונים.", "Interactive notebooks for data analysis.",
                ["Notebook"], ["jupyterlab", "jupyternotebook"]),
    "powerbi": ("database", "כלי BI של מיקרוסופט להדמיית נתונים ודוחות.", "Microsoft BI for reports and dashboards.",
                ["BI"], ["powerbidesktop", "pbidesktop"]),
    "rstudio": ("database", "סביבת פיתוח לשפת R וניתוח סטטיסטי.", "IDE for R and statistical computing.",
                ["R"], []),
    "figma": ("design", "כלי עיצוב ממשקים ואב-טיפוס.", "Interface design and prototyping.", ["UI/UX"], []),
    "gimp": ("design", "תוכנת עריכת תמונות קוד פתוח.", "Open-source image editor.", ["Image"], []),
    "inkscape": ("design", "עורך גרפיקה וקטורית.", "Vector graphics editor.", ["Vector"], []),
    "blender": ("design", "תוכנת תלת-ממד להדמיה, אנימציה ורינדור.", "3D modeling, animation and rendering.",
                ["3D"], []),
    "krita": ("design", "תוכנת ציור דיגיטלי ואיור.", "Digital painting and illustration.", ["Illustration"], []),
    "paintnet": ("design", "עורך תמונות פשוט ומהיר ל-Windows.", "Simple, fast image editor.", ["Image"],
                 ["paintdotnet"]),
    "drawio": ("design", "כלי לשרטוט דיאגרמות ותרשימי ארכיטקטורה.", "Diagrams and architecture drawings.",
               ["Diagrams"], ["diagramsnet", "drawiodesktop"]),
    "teams": ("tools", "פלטפורמת תקשורת ושיתוף פעולה של מיקרוסופט.", "Microsoft collaboration platform.",
              ["Collaboration"], ["microsoftteams", "msteams"]),
    "altium": ("design", "תוכנת תכנון מעגלים מודפסים (PCB) וסכמות חשמליות.", "PCB and schematic design suite.",
               ["PCB", "EDA"], ["altiumdesigner", "altiuminstaller"]),
    "kicad": ("design", "חבילת קוד פתוח לתכנון סכמות ומעגלים מודפסים.", "Open-source schematic and PCB design suite.",
              ["PCB", "EDA"], []),
    "stm32cube": ("code", "כלי ST לפיתוח, קינפוג וצריבה של מיקרו-בקרים STM32.",
                  "ST tools to configure, develop and flash STM32 microcontrollers.", ["Embedded", "MCU"],
                  ["stm32cubeide", "stm32cubemx", "stm32cubeprogrammer", "stm32cubeprog"]),
    "nmap": ("tools", "סורק רשת לגילוי מארחים, פורטים ושירותים.", "Network scanner for hosts, ports and services.",
             ["Network", "Security"], ["zenmap"]),
    "sysinternals": ("tools", "אוסף כלי האבחון והניהול של מיקרוסופט ל-Windows.",
                     "Microsoft's suite of Windows troubleshooting and admin utilities.", ["Windows", "Diagnostics"],
                     ["sysinternalssuite"]),
    "powershell": ("tools", "מעטפת ושפת סקריפטים חוצת פלטפורמות של מיקרוסופט (PowerShell 7).",
                   "Microsoft's cross-platform shell and scripting language (PowerShell 7).", ["Shell", "Scripting"],
                   ["pwsh", "powershell7", "powershellcore"]),
    "trellix": ("tools", "סוכן אבטחת תחנות קצה (לשעבר McAfee).", "Endpoint security agent (formerly McAfee).",
                ["Security", "Agent"], ["trellixagent", "mcafeeagent", "mcafee"]),
    "meshagent": ("tools", "סוכן ניהול ותמיכה מרחוק של MeshCentral.", "MeshCentral remote management agent.",
                  ["Remote", "Agent"], ["meshcentral", "meshcentralagent"]),
    "cacerts": ("tools", "תעודות ה-CA הארגוניות להתקנה בתחנה.", "Organizational CA certificates for workstations.",
                ["Certificates", "PKI"], ["cacertificates", "rootca", "rootcertificates", "certificates"]),
}

# Local SVG fallbacks in static/icons/<name>.svg, keyed by known application.
BUILTIN_APP_ICONS: Dict[str, str] = {
    "vscode": "vscode", "visualstudio": "visualstudio", "intellij": "jetbrains", "pycharm": "jetbrains",
    "androidstudio": "android", "eclipse": "java", "git": "git", "python": "python", "anaconda": "python",
    "jupyter": "python", "nodejs": "nodejs", "java": "java", "golang": "go", "dotnet": "dotnet",
    "postman": "postman", "docker": "docker", "wsl": "linux", "terraform": "terraform", "kubectl": "kubernetes",
    "helm": "kubernetes", "lens": "kubernetes", "chrome": "chrome", "firefox": "firefox", "edge": "edge",
    "pgadmin": "postgres", "dbeaver": "database", "ssms": "sqlserver", "sqlserver": "sqlserver",
    "mongodbcompass": "mongodb", "redis": "redis", "mysqlworkbench": "mysql", "putty": "terminal",
    "mobaxterm": "terminal", "winscp": "terminal", "filezilla": "terminal", "7zip": "archive",
    "winrar": "archive", "notepadplusplus": "editor", "sublimetext": "editor", "vim": "editor",
    "obsidian": "editor", "selenium": "chrome", "jmeter": "java", "ansible": "terminal",
    "nmap": "terminal", "sysinternals": "terminal", "powershell": "terminal",
}

# Selectable built-in icons for platforms and stacks in the admin UI.
BUILTIN_ICON_NAMES: List[str] = sorted(set(BUILTIN_APP_ICONS.values()) | {
    "gitlab", "jira", "confluence", "mattermost", "nexus",
})

# Role presets shown first on the Bundles tab; existing installations receive them once (db.init_db).
ROLE_BUNDLES: List[Dict[str, Any]] = [
    {"id": "electronics", "icon": "cpu", "color": "#F59E0B",
     "name_en": "Electronics Developer", "name_he": "מפתח אלקטרוניקה",
     "description_en": "PCB design, STM32 toolchain, serial/SSH access and protocol analysis.",
     "description_he": "תכנון מעגלים, כלי STM32, גישה טורית ו-SSH וניתוח פרוטוקולים.",
     "apps": ["altium", "kicad", "stm32cube", "wireshark", "putty"]},
    {"id": "software", "icon": "code", "color": "#6366F1",
     "name_en": "Software Developer", "name_he": "מפתח תוכנה",
     "description_en": "Editor, version control, containers and the core runtimes.",
     "description_he": "עורך קוד, ניהול גרסאות, קונטיינרים וסביבות ההרצה המרכזיות.",
     "apps": ["vscode", "git", "docker", "python", "nodejs"]},
    {"id": "sysadmin", "icon": "terminal", "color": "#0EA5E9",
     "name_en": "SysAdmin / NetOps", "name_he": "SysAdmin / NetOps",
     "description_en": "Remote terminals, file transfer, network scanning and Windows diagnostics.",
     "description_he": "טרמינלים מרוחקים, העברת קבצים, סריקת רשת וכלי אבחון ל-Windows.",
     "apps": ["mobaxterm", "nmap", "winscp", "sysinternals", "powershell"]},
    {"id": "essentials", "icon": "shield", "color": "#10B981",
     "name_en": "Essentials (Infra/Agents)", "name_he": "חיוניים (תשתית וסוכנים)",
     "description_en": "Mandatory workstation agents and the organizational CA certificates.",
     "description_he": "סוכני חובה לתחנה ותעודות ה-CA הארגוניות.",
     "apps": ["trellix", "meshagent", "cacerts"]},
]

DEFAULT_BUNDLES: List[Dict[str, Any]] = ROLE_BUNDLES + [
    {"id": "fullstack", "icon": "code", "color": "#6366F1",
     "name_en": "Fullstack Developer", "name_he": "מפתח Fullstack",
     "description_en": "Editors, runtimes and API tooling for day-one productivity.",
     "description_he": "עורכי קוד, סביבות הרצה וכלי API - מוכנים מהיום הראשון.",
     "apps": ["vscode", "git", "python", "nodejs", "java", "intellij", "pycharm", "postman", "notepadplusplus"]},
    {"id": "devops", "icon": "server", "color": "#0EA5E9",
     "name_en": "DevOps Engineer", "name_he": "מהנדס DevOps",
     "description_en": "Containers, IaC, Kubernetes and remote-access essentials.",
     "description_he": "קונטיינרים, תשתית כקוד, Kubernetes וגישה מרחוק.",
     "apps": ["vscode", "git", "python", "wsl", "docker", "terraform", "kubectl", "helm", "lens", "putty",
              "winscp", "mobaxterm"]},
    {"id": "data", "icon": "chart", "color": "#10B981",
     "name_en": "Data Engineer", "name_he": "מהנדס דאטה",
     "description_en": "Python, notebooks, SQL clients and BI for analysts.",
     "description_he": "פייתון, מחברות, לקוחות SQL וכלי BI לאנליסטים.",
     "apps": ["python", "anaconda", "jupyter", "dbeaver", "ssms", "pgadmin", "mongodbcompass", "powerbi", "rstudio"]},
    {"id": "qa", "icon": "check", "color": "#8B5CF6",
     "name_en": "QA Automation", "name_he": "בודק תוכנה ואוטומציה",
     "description_en": "API testing, browser automation, load testing and traffic analysis.",
     "description_he": "בדיקות API, אוטומציית דפדפן, בדיקות עומסים וניתוח תעבורה.",
     "apps": ["postman", "chrome", "firefox", "edge", "jmeter", "selenium", "soapui", "wireshark"]},
    {"id": "design", "icon": "design", "color": "#EC4899",
     "name_en": "UI/UX Designer", "name_he": "מעצב UI/UX",
     "description_en": "Graphics, illustration, 3D and architecture diagrams.",
     "description_he": "גרפיקה, איור, תלת-ממד ושרטוט דיאגרמות.",
     "apps": ["figma", "gimp", "inkscape", "blender", "krita", "paintnet", "drawio", "obs"]},
]

DEFAULT_PLATFORMS: List[Dict[str, Any]] = [
    {"name": "GitLab", "url": "https://gitlab.example.com", "icon": "gitlab", "color": "#FC6D26",
     "description_he": "ניהול קוד מקור, Merge Requests ו-CI/CD.",
     "description_en": "Source control, merge requests and CI/CD."},
    {"name": "Jira", "url": "https://jira.example.com", "icon": "jira", "color": "#2684FF",
     "description_he": "ניהול משימות, ספרינטים ובאגים.",
     "description_en": "Issues, sprints and bug tracking."},
    {"name": "Confluence", "url": "https://confluence.example.com", "icon": "confluence", "color": "#1D7AFC",
     "description_he": "תיעוד, ויקי ארגוני ובסיס ידע.",
     "description_en": "Documentation, wiki and knowledge base."},
    {"name": "Mattermost", "url": "https://mattermost.example.com", "icon": "mattermost", "color": "#1E325C",
     "description_he": "צ'אט ארגוני ותקשורת צוותים.",
     "description_en": "Team chat and collaboration."},
    {"name": "Nexus Repository", "url": "https://nexus.example.com", "icon": "nexus", "color": "#1FA67A",
     "description_he": "מאגר חבילות פנימי: PyPI, npm, Maven, Docker.",
     "description_en": "Internal package registry: PyPI, npm, Maven, Docker."},
]

# Stack glyphs rendered by the frontend icon set.
STACK_GLYPHS: List[str] = ["code", "server", "chart", "check", "design", "database", "terminal", "package",
                           "shield", "cpu", "globe", "layers"]

CORE_APP_KEYS = {"vscode", "git", "python", "nodejs", "java", "docker", "chrome", "postman", "visualstudio",
                 "intellij", "pycharm", "dbeaver"}


def normalize_key(value: str) -> str:
    value = value.lower().replace("+", "p")
    return re.sub(r"[^a-z0-9\u0590-\u05ff]", "", value)


ALIAS_MAP: Dict[str, str] = {}
for _key, (_c, _dh, _de, _t, _aliases) in KNOWN_APPS.items():
    ALIAS_MAP[_key] = _key
    for _alias in _aliases:
        ALIAS_MAP.setdefault(normalize_key(_alias), _key)
_ALIASES_BY_LENGTH = sorted(ALIAS_MAP, key=len, reverse=True)


def match_known_app(name: str) -> Optional[str]:
    norm = normalize_key(name)
    if not norm:
        return None
    if norm in ALIAS_MAP:
        return ALIAS_MAP[norm]
    for alias in _ALIASES_BY_LENGTH:
        if len(alias) >= 4 and alias in norm:
            return ALIAS_MAP[alias]
    return None


def guess_category(name: str) -> str:
    n = name.lower()
    rules = [
        ("database", ("sql", "db", "mongo", "redis", "postgres", "oracle", "data", "bi", "elastic")),
        ("code", ("studio", "code", "ide", "dev", "sdk", "jdk", "compiler", "python", "java", "git")),
        ("text", ("edit", "note", "text", "pad", "office", "pdf", "word", "reader", "markdown")),
        ("design", ("design", "paint", "photo", "adobe", "draw", "image", "3d", "video", "illustr", "graphic")),
    ]
    for category, keywords in rules:
        if any(k in n for k in keywords):
            return category
    return "tools"


def resolve_category(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().lower()
    if raw in CATEGORY_IDS:
        return raw
    return CATEGORY_ALIASES.get(raw) or CATEGORY_ALIASES.get(value.strip())


def category_labels(category: str) -> Tuple[str, str]:
    for cid, he, en in CATEGORIES:
        if cid == category:
            return he, en
    return "כלים ותשתית", "Tools & Infra"
