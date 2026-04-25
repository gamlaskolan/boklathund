# boklathund.py
# Kör med: streamlit run boklathund.py

import re
import html
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests
import streamlit as st
import streamlit.components.v1 as components


# ------------------------------------------------------------
# Grundinställningar för appen
# ------------------------------------------------------------

st.set_page_config(
    page_title="Boklathund – Snabbguide till böcker & artiklar",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ------------------------------------------------------------
# Datamodell: en enkel struktur för bokresultat
# ------------------------------------------------------------

@dataclass
class Book:
    title: str
    authors: str
    year: str
    description: str
    thumbnail: str
    info_link: str


# ------------------------------------------------------------
# HTML-parser för enkel artikel-/webbtext
# ------------------------------------------------------------

class SimpleTextExtractor(HTMLParser):
    """Plockar ut synlig text från enklare webbsidor."""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tag = False

    def handle_starttag(self, tag, attrs):
        # Script/style/nav/footer ger oftast brus.
        if tag in {"script", "style", "nav", "footer", "header"}:
            self.skip_tag = True

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer", "header"}:
            self.skip_tag = False

    def handle_data(self, data):
        if not self.skip_tag:
            clean_text = data.strip()
            if clean_text:
                self.text_parts.append(clean_text)

    def get_text(self):
        return " ".join(self.text_parts)


# ------------------------------------------------------------
# Hjälpfunktioner
# ------------------------------------------------------------

def init_session_state():
    # Streamlit sparar detta mellan klick medan appen är öppen.
    if "saved_guides" not in st.session_state:
        st.session_state.saved_guides = []


def clean_text(text: str) -> str:
    # Tar bort HTML, extra blanksteg och gör texten lättare att läsa.
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def short_text(text: str, max_chars: int = 900) -> str:
    # Klipper text snyggt så UI:t inte blir för långt.
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def extract_year(published_date: str) -> str:
    # Google Books kan ge "2020-04-12" eller bara "2020".
    match = re.search(r"\d{4}", published_date or "")
    return match.group(0) if match else "Okänt år"


def split_sentences(text: str) -> list[str]:
    # Enkel men fungerande meningsdelning utan extra bibliotek.
    text = clean_text(text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [sentence.strip() for sentence in sentences if len(sentence.strip()) > 20]


def make_summary(text: str, max_sentences: int = 4) -> str:
    # Enkel sammanfattning: tar de första tydliga meningarna.
    sentences = split_sentences(text)
    if not sentences:
        return "Ingen sammanfattning kunde skapas från tillgänglig text."
    return " ".join(sentences[:max_sentences])


def make_keywords(text: str, limit: int = 12) -> list[str]:
    # Skapar nyckelord genom att räkna ord som inte är stoppord.
    stopwords = {
        "och", "att", "det", "som", "för", "med", "till", "den", "ett", "har",
        "this", "that", "with", "from", "and", "the", "are", "was", "were",
        "you", "your", "about", "into", "their", "they", "his", "her", "its",
    }

    words = re.findall(r"[A-Za-zÅÄÖåäö]{4,}", text.lower())
    counts = {}

    for word in words:
        if word not in stopwords:
            counts[word] = counts.get(word, 0) + 1

    sorted_words = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [word for word, _ in sorted_words[:limit]]


def is_url(text: str) -> bool:
    # Kontrollerar om användaren klistrat in en webblänk.
    parsed = urlparse(text.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


# ------------------------------------------------------------
# Internetfunktioner
# ------------------------------------------------------------

def search_google_books(query: str, max_results: int = 6) -> list[Book]:
    # Google Books kräver ingen API-nyckel för enkel sökning.
    url = "https://www.googleapis.com/books/v1/volumes"

    params = {
        "q": query,
        "maxResults": max_results,
        "printType": "books",
        "langRestrict": "sv",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as error:
        st.error(f"Kunde inte söka i Google Books: {error}")
        return []
    except ValueError:
        st.error("Google Books svarade inte med giltig JSON.")
        return []

    books = []

    for item in data.get("items", []):
        volume = item.get("volumeInfo", {})

        image_links = volume.get("imageLinks", {})
        thumbnail = image_links.get("thumbnail", "").replace("http://", "https://")

        books.append(
            Book(
                title=volume.get("title", "Okänd titel"),
                authors=", ".join(volume.get("authors", ["Okänd författare"])),
                year=extract_year(volume.get("publishedDate", "")),
                description=clean_text(volume.get("description", "")),
                thumbnail=thumbnail,
                info_link=volume.get("infoLink", ""),
            )
        )

    return books


def fetch_text_from_url(url: str) -> str:
    # Hämtar enkel text från en webbsida. Fungerar bäst på öppna artiklar.
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        parser = SimpleTextExtractor()
        parser.feed(response.text)

        return short_text(parser.get_text(), 5000)

    except requests.RequestException as error:
        st.error(f"Kunde inte hämta länken: {error}")
        return ""


# ------------------------------------------------------------
# Lathund-generator
# ------------------------------------------------------------

def generate_guide(title: str, author: str, source_text: str) -> tuple[str, str]:
    # Allt här är enkel regelbaserad logik så nybörjare kan bygga vidare senare.
    summary = make_summary(source_text)
    keywords = make_keywords(source_text)

    themes = keywords[:6] or ["tema saknas"]
    search_index = keywords[:12] or ["sökord saknas"]

    guide = f"""# {title}

## 📖 Översikt
{summary}

## 🔑 Nyckelteman & huvudbudskap
{chr(10).join(f"- {theme.title()}" for theme in themes)}

## 📋 Kapitelguide / huvuddelar
- Början: introducerar ämnet, kontexten och huvudfrågan.
- Mitten: utvecklar idéerna, exemplen eller argumenten.
- Slut: knyter ihop budskapet och visar vad läsaren bör ta med sig.

## 💡 Praktiska tips / takeaways
- Läs först översikten för att förstå helheten.
- Sök efter nyckelorden nedan när du vill hitta viktiga stycken snabbt.
- Markera exempel, definitioner och återkommande begrepp.
- Skriv egna anteckningar under varje huvuddel.

## 📌 Viktiga citat
- Inga verifierade citat hittades automatiskt.
- Lägg till exakta citat manuellt om du har tillgång till originaltexten.

## 🔍 Snabbsök-index
{chr(10).join(f"- {word}" for word in search_index)}

---
Källa/författare: {author}
"""

    return summary, guide


# ------------------------------------------------------------
# UI-hjälpare
# ------------------------------------------------------------

def copy_button(label: str, text: str, height: int = 48):
    # Streamlit har ingen inbyggd clipboard-knapp, så vi använder lite HTML/JS.
    safe_text = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    components.html(
        f"""
        <button onclick="navigator.clipboard.writeText(`{safe_text}`)"
                style="
                    width:100%;
                    height:{height}px;
                    border:0;
                    border-radius:10px;
                    background:#1f6feb;
                    color:white;
                    font-size:16px;
                    font-weight:700;
                    cursor:pointer;">
            {label}
        </button>
        """,
        height=height + 10,
    )


def apply_css():
    # Lite CSS gör appen mer professionell utan att komplicera Python-koden.
    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 2rem;
            max-width: 1200px;
        }
        .book-card {
            border: 1px solid #e6e8eb;
            border-radius: 12px;
            padding: 1rem;
            background: #ffffff;
            box-shadow: 0 2px 10px rgba(0,0,0,0.04);
        }
        .small-muted {
            color: #687078;
            font-size: 0.92rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def save_guide(title: str, summary: str, guide: str):
    # Sparar aktuell lathund i session_state.
    st.session_state.saved_guides.append(
        {
            "title": title,
            "summary": summary,
            "guide": guide,
        }
    )
    st.success("Lathunden sparades i Mina lathundar.")


# ------------------------------------------------------------
# Sidor
# ------------------------------------------------------------

def search_page():
    st.title("📚 Boklathund – Snabbguide till böcker & artiklar")
    st.caption("Sök böcker via Google Books eller klistra in artikeltext/länk.")

    query = st.text_input(
        "Sök efter boktitel, författare eller nyckelord",
        placeholder="Exempel: Atomic Habits, Selma Lagerlöf, ledarskap...",
    )

    extra_text = st.text_area(
        "Artikel, text eller länk",
        placeholder="Klistra in en artikeltext eller en https-länk här...",
        height=160,
    )

    search_clicked = st.button("Sök på internet", type="primary", use_container_width=True)

    if search_clicked:
        if not query and not extra_text:
            st.warning("Skriv en sökning, klistra in text eller ange en länk.")
            return

        # Artikel-/textläge.
        if extra_text:
            article_text = fetch_text_from_url(extra_text) if is_url(extra_text) else extra_text
            article_title = query or "Artikel / inklistrad text"

            summary, guide = generate_guide(
                title=article_title,
                author="Egen text eller öppen webbsida",
                source_text=article_text,
            )

            st.subheader("Sammanfattning")
            st.info(summary)

            copy_button("📋 Kopiera hela lathunden för Google Docs", guide, 56)
            copy_button("📋 Kopiera bara sammanfattningen", summary, 48)

            with st.expander("Visa Markdown-lathund", expanded=True):
                st.markdown(guide)

            if st.button("Spara i Mina lathundar", use_container_width=True):
                save_guide(article_title, summary, guide)

            return

        # Bokläge.
        books = search_google_books(query)

        if not books:
            st.warning("Ingen exakt bok hittades. Testa en kortare titel, författarnamn eller engelska sökord.")
            return

        st.subheader("Bästa träffar")

        for index, book in enumerate(books):
            with st.container():
                left, right = st.columns([1, 4], vertical_alignment="top")

                with left:
                    if book.thumbnail:
                        st.image(book.thumbnail, width=120)
                    else:
                        st.write("📘 Inget omslag")

                with right:
                    st.markdown(f"### {book.title}")
                    st.markdown(f"<span class='small-muted'>{book.authors} · {book.year}</span>", unsafe_allow_html=True)
                    st.write(short_text(book.description or "Ingen beskrivning hittades.", 700))

                    source_text = f"{book.title}. {book.authors}. {book.description}"
                    summary, guide = generate_guide(book.title, book.authors, source_text)

                    with st.expander("Skapa och visa lathund"):
                        st.subheader("Sammanfattning")
                        st.info(summary)

                        copy_button("📋 Kopiera hela lathunden för Google Docs", guide, 56)
                        copy_button("📋 Kopiera bara sammanfattningen", summary, 48)

                        st.markdown(guide)

                        if st.button(f"Spara '{book.title}'", key=f"save_{index}", use_container_width=True):
                            save_guide(book.title, summary, guide)

                    if book.info_link:
                        st.link_button("Öppna i Google Books", book.info_link)


def saved_guides_page():
    st.title("Mina lathundar")

    if not st.session_state.saved_guides:
        st.info("Du har inte sparat några lathundar ännu.")
        return

    for index, item in enumerate(st.session_state.saved_guides):
        with st.expander(item["title"], expanded=False):
            st.subheader("Sammanfattning")
            st.write(item["summary"])

            copy_button("📋 Kopiera hela lathunden för Google Docs", item["guide"], 56)
            copy_button("📋 Kopiera bara sammanfattningen", item["summary"], 48)

            st.markdown(item["guide"])

            if st.button("Ta bort", key=f"delete_{index}"):
                st.session_state.saved_guides.pop(index)
                st.rerun()


def how_it_works_page():
    st.title("Hur appen fungerar")

    st.markdown(
        """
        ### Så här använder du lathunden i Google Docs

        1. Sök efter en bok eller klistra in en artikeltext/länk.
        2. Öppna lathunden.
        3. Klicka på **Kopiera hela lathunden för Google Docs**.
        4. Öppna Google Docs.
        5. Klistra in texten.
        6. Lägg gärna till egna citat, sidnummer och anteckningar.

        ### Viktigt

        Appen använder gratis Google Books-data och enkel textanalys.
        Den laddar inte ner hela böcker och ersätter inte originalkällan.
        """
    )


# ------------------------------------------------------------
# Appens startpunkt
# ------------------------------------------------------------

def main():
    init_session_state()
    apply_css()

    st.sidebar.title("Meny")
    page = st.sidebar.radio(
        "Välj sida",
        ["Sök", "Mina lathundar", "Hur appen fungerar"],
    )

    st.sidebar.divider()
    st.sidebar.caption("Byggd med Streamlit + requests.")

    if page == "Sök":
        search_page()
    elif page == "Mina lathundar":
        saved_guides_page()
    else:
        how_it_works_page()


if __name__ == "__main__":
    main()
