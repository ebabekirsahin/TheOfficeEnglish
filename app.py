import os
import re
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="The Office English", page_icon="📺", layout="wide")

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "The_Office_lines.csv"
DB = ROOT / "data" / "progress.db"

st.markdown("""
<style>
.block-container {max-width: 1400px; padding-top: 2rem;}
.quote {padding: 14px 18px; border-radius: 12px; background: rgba(128,128,128,.10); margin: 8px 0;}
.speaker {font-weight: 700; font-size: 1.05rem;}
.small {opacity: .72; font-size: .88rem;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(show_spinner="Loading The Office transcript…")
def load_data():
    if not DATA.exists():
        return pd.DataFrame(columns=["id","season","episode","scene","line_text","speaker","deleted"])
    df = pd.read_csv(DATA)
    for c in ["season", "episode", "scene"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    df["line_text"] = df["line_text"].fillna("").astype(str).str.strip()
    df["speaker"] = df["speaker"].fillna("Unknown").astype(str).str.strip()
    if "deleted" in df.columns:
        df = df[df["deleted"].astype(str).str.lower().isin(["false", "0", "nan"]) | df["deleted"].isna()]
    return df[df["line_text"].ne("")].drop_duplicates(subset=["season","episode","scene","speaker","line_text"]).reset_index(drop=True)

def db():
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS notes (kind TEXT, item TEXT, note TEXT, PRIMARY KEY(kind,item))")
    con.execute("CREATE TABLE IF NOT EXISTS progress (item TEXT PRIMARY KEY, status TEXT)")
    con.commit()
    return con

def save_note(kind, item, note):
    con=db(); con.execute("INSERT OR REPLACE INTO notes VALUES (?,?,?)", (kind,item,note)); con.commit(); con.close()

def get_note(kind,item):
    con=db(); row=con.execute("SELECT note FROM notes WHERE kind=? AND item=?",(kind,item)).fetchone(); con.close(); return row[0] if row else ""

def mark(item,status="learned"):
    con=db(); con.execute("INSERT OR REPLACE INTO progress VALUES (?,?)",(item,status)); con.commit(); con.close()

def learned_count():
    con=db(); n=con.execute("SELECT COUNT(*) FROM progress WHERE status='learned'").fetchone()[0]; con.close(); return n

def normalize(text):
    return re.sub(r"[^a-z0-9' -]", " ", text.lower())

# Curated high-frequency patterns. The app also discovers occurrences directly from the transcript.
PHRASAL = [
    "figure out","find out","get back","get in","get out","give up","go on","hang out","look for","look into",
    "look like","pick up","put off","run into","set up","take care of","take over","turn out","work out",
    "come back","come in","come on","come up","bring up","call back","carry on","check out","end up","fill out",
    "go ahead","grow up","hold on","keep up","leave out","make up","move on","point out","show up","sit down",
    "stand up","talk about","throw away","try out","wake up","watch out","write down"
]
COMMON = [
    "what's up","are you kidding me","come on","no way","my bad","hold on","sounds good","let me know","you know what",
    "i guess","i mean","give me a break","what do you mean","are you serious","just kidding","that's fine","of course",
    "no problem","kind of","sort of","right away","at least","by the way","for sure","i don't know","i don't think so"
]
IDIOMS = [
    "break the ice","piece of cake","under the weather","hit the nail on the head","give me a break","pull someone's leg",
    "once in a blue moon","on the same page","go the extra mile","get the ball rolling","a win-win","call it a day",
    "back to square one","out of the blue","in hot water","cut corners","the last straw","bite the bullet"
]

LEVEL_HINTS = {"figure out":"B1","find out":"A2","get back":"A2","give up":"A2","look for":"A2","pick up":"A2","put off":"B1","run into":"B1","set up":"B1","take over":"B1","work out":"B1","on the same page":"B2","call it a day":"B1"}

def occurrences(df, terms):
    rows=[]
    texts=df["line_text"].str.lower()
    for term in terms:
        mask=texts.str.contains(re.escape(term), regex=True, na=False)
        if mask.any():
            sub=df.loc[mask, ["season","episode","scene","speaker","line_text"]].head(1).copy()
            sub["term"]=term
            rows.append(sub)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

df=load_data()
if df.empty:
    st.error("Dataset bulunamadı. `data/The_Office_lines.csv` dosyasını repository'ye ekleyin.")
    st.stop()

st.sidebar.title("📺 The Office English")
page=st.sidebar.radio("Go to", ["🏠 Dashboard","🎬 Seasons & Episodes","📖 Reading Mode","📚 Vocabulary & Expressions","🔄 Phrasal Verbs","💡 Idioms","🧠 Study Mode","📝 My Notes"])
st.sidebar.divider()
st.sidebar.caption(f"{len(df):,} dialogue lines loaded")

if page=="🏠 Dashboard":
    st.title("📺 The Office English")
    st.subheader("Learn real-life English from the show you love.")
    seasons=df.season.nunique(); eps=df[["season","episode"]].drop_duplicates().shape[0]; chars=df.speaker.nunique()
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Seasons", seasons); c2.metric("Episodes", eps); c3.metric("Characters", chars); c4.metric("Learned", learned_count())
    st.divider()
    st.markdown("### 🎯 Recommended workflow")
    st.info("Pick an episode → read the dialogue → inspect useful expressions → save notes → take the study quiz. Focus on context and repeated exposure rather than memorizing isolated words.")
    st.markdown("### 🔎 Quick search")
    q=st.text_input("Search any quote, word or expression")
    if q:
        res=df[df.line_text.str.contains(re.escape(q),case=False,regex=True,na=False)].head(30)
        st.write(f"Found {len(res)} results")
        for _,r in res.iterrows():
            st.markdown(f'<div class="quote"><div class="speaker">{r.speaker}</div><div>{r.line_text}</div><div class="small">S{r.season:02d}E{r.episode:02d} · Scene {r.scene}</div></div>', unsafe_allow_html=True)

elif page=="🎬 Seasons & Episodes":
    st.title("🎬 Seasons & Episodes")
    season=st.selectbox("Season", sorted(df.season.unique()), format_func=lambda x:f"Season {x}")
    edf=df[df.season==season]
    episodes=sorted(edf.episode.unique())
    ep=st.selectbox("Episode", episodes, format_func=lambda x:f"S{season:02d}E{x:02d}")
    x=edf[edf.episode==ep]
    scenes=sorted(x.scene.unique())
    st.markdown(f"## S{season:02d}E{ep:02d}")
    st.caption(f"{len(x):,} dialogue lines · {len(scenes)} scenes · {x.speaker.nunique()} characters")
    for scene in scenes:
        with st.expander(f"Scene {scene}", expanded=(scene==scenes[0])):
            for _,r in x[x.scene==scene].iterrows():
                st.markdown(f"**{r.speaker}:** {r.line_text}")

elif page=="📖 Reading Mode":
    st.title("📖 Reading Mode")
    season=st.selectbox("Season", sorted(df.season.unique()), key="read_s")
    eps=sorted(df[df.season==season].episode.unique())
    ep=st.selectbox("Episode", eps, key="read_e")
    x=df[(df.season==season)&(df.episode==ep)].copy()
    hide_tr=st.toggle("Hide Turkish / learning hints", True)
    highlight=st.toggle("Highlight expressions", False)
    for scene in sorted(x.scene.unique()):
        st.markdown(f"### Scene {scene}")
        for _,r in x[x.scene==scene].iterrows():
            txt=r.line_text
            if highlight:
                for term in COMMON+PHRASAL+IDIOMS:
                    txt=re.sub(rf"(?i)\b({re.escape(term)})\b", r"**\1**", txt)
            st.markdown(f"**{r.speaker}:** {txt}")
            if not hide_tr:
                st.caption("Click the vocabulary/expression pages to study this line in context.")

elif page=="📚 Vocabulary & Expressions":
    st.title("📚 Vocabulary & Everyday Expressions")
    tab1,tab2=st.tabs(["Everyday Expressions","Vocabulary Search"])
    with tab1:
        occ=occurrences(df, COMMON)
        if occ.empty: st.warning("No expressions found.")
        else:
            for _,r in occ.iterrows():
                with st.expander(f"💬 {r.term}"):
                    st.write(f"**Example from the transcript:** {r.line_text}")
                    st.caption(f"S{r.season:02d}E{r.episode:02d} · {r.speaker}")
                    st.markdown(f"**Natural Turkish:** {r.term} — bağlama göre değişir; dizideki cümleyi esas alın.")
                    note=st.text_area("My note", get_note("expression",r.term), key="n_"+r.term)
                    if st.button("Save note", key="b_"+r.term): save_note("expression",r.term,note); st.success("Saved")
    with tab2:
        q=st.text_input("Search a word")
        if q:
            res=df[df.line_text.str.contains(re.escape(q),case=False,regex=True,na=False)].head(50)
            for _,r in res.iterrows(): st.markdown(f"**{r.speaker}:** {r.line_text}  \n`S{r.season:02d}E{r.episode:02d} · Scene {r.scene}`")

elif page=="🔄 Phrasal Verbs":
    st.title("🔄 Phrasal Verbs")
    occ=occurrences(df, PHRASAL)
    if not occ.empty:
        for _,r in occ.iterrows():
            term=r.term; level=LEVEL_HINTS.get(term,"B1–B2")
            with st.expander(f"{term} · {level}"):
                st.markdown(f"**Meaning:** {term} has a context-dependent meaning. Study the example below rather than translating word-by-word.")
                st.markdown(f"> {r.line_text}")
                st.caption(f"S{r.season:02d}E{r.episode:02d} · {r.speaker}")
                if st.button("✓ Mark learned", key="pv_"+term): mark("phrasal:"+term); st.success("Learned")

elif page=="💡 Idioms":
    st.title("💡 Idioms")
    occ=occurrences(df, IDIOMS)
    if occ.empty: st.info("No curated idiom occurrences were found in this dataset.")
    for _,r in occ.iterrows():
        with st.expander(r.term):
            st.write(f"**Example:** {r.line_text}")
            st.caption(f"S{r.season:02d}E{r.episode:02d} · {r.speaker}")
            st.write("**Tip:** Learn the whole expression and the situation in which it is used.")

elif page=="🧠 Study Mode":
    st.title("🧠 Study Mode")
    st.write("A small active-recall session based on your transcript.")
    if "quiz" not in st.session_state:
        st.session_state.quiz=df.sample(min(10,len(df)), random_state=42).reset_index(drop=True)
        st.session_state.qi=0
        st.session_state.score=0
    qn=st.session_state.qi
    if qn>=len(st.session_state.quiz):
        st.success(f"Finished! Score: {st.session_state.score}/{len(st.session_state.quiz)}")
        if st.button("Start again"):
            del st.session_state.quiz; st.rerun()
    else:
        r=st.session_state.quiz.iloc[qn]
        st.progress(qn/len(st.session_state.quiz))
        st.caption(f"Question {qn+1} / {len(st.session_state.quiz)} · S{r.season:02d}E{r.episode:02d}")
        st.markdown(f"### Who said this?\n\n> {r.line_text}")
        opts=[r.speaker]+list(df.speaker[df.speaker.ne(r.speaker)].drop_duplicates().sample(3, random_state=qn).values)
        choice=st.radio("Choose", opts, key=f"choice{qn}")
        if st.button("Check answer", key=f"check{qn}"):
            if choice==r.speaker: st.success("Correct!"); st.session_state.score+=1
            else: st.error(f"Not quite. It was **{r.speaker}**.")
            mark(f"quote:{r.id}")
            st.session_state.qi+=1
            st.rerun()

elif page=="📝 My Notes":
    st.title("📝 My Notes")
    con=db(); rows=con.execute("SELECT kind,item,note FROM notes ORDER BY rowid DESC").fetchall(); con.close()
    if not rows: st.info("No notes yet. Add notes from the Expressions and Phrasal Verbs pages.")
    for kind,item,note in rows:
        st.markdown(f"### {item}")
        st.caption(kind)
        st.write(note)

st.sidebar.divider()
st.sidebar.caption("The Office English · transcript learning tool")
