"""
Generate synthetic Salt Bank support-call data for VoiceScribe.

SYNTHETIC DATA ONLY — no real customers, no real audio, no PII.
Produces:
  - data/synthetic/calls_metadata.jsonl   (one row per call)
  - data/synthetic/transcripts/<call_id>.txt  (RO/EN transcript text)

Optionally, if `pyttsx3` (offline TTS) is installed and --audio is passed,
renders a .wav per call so the pipeline can be exercised end-to-end with the
Whisper STT layer. Without --audio, transcripts stand in for the STT output.

Usage:
    python generate_synthetic_calls.py --n 40
    python generate_synthetic_calls.py --n 40 --audio
"""
from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "synthetic"
TRANSCRIPTS = OUT / "transcripts"

AGENTS = [
    "A. Popescu", "M. Ionescu", "D. Georgescu", "R. Stan",
    "E. Marin", "C. Dumitru", "L. Nagy", "S. Novak",
]

# Category -> (English template turns, Romanian template turns)
SCENARIOS = {
    "card_lost": (
        [
            ("agent", "Salt Bank, good afternoon, how can I help?"),
            ("customer", "Hi, I lost my card yesterday and I want to block it."),
            ("agent", "I'm sorry to hear that. I can block it right now. Can you confirm your name and date of birth?"),
            ("customer", "Yes, it's {name}, born on the 14th of March."),
            ("agent", "Thank you. Your card ending 4471 is now blocked. Shall I order a replacement?"),
            ("customer", "Yes please, to my home address."),
            ("agent", "Done. It arrives in 3 to 5 working days. Anything else?"),
            ("customer", "No, thank you very much."),
        ],
        [
            ("agent", "Salt Bank, bună ziua, cu ce vă pot ajuta?"),
            ("customer", "Bună, mi-am pierdut cardul ieri și vreau să îl blochez."),
            ("agent", "Îmi pare rău. Îl blochez imediat. Îmi confirmați numele și data nașterii?"),
            ("customer", "Da, sunt {name}, născut pe 14 martie."),
            ("agent", "Mulțumesc. Cardul care se termină în 4471 este acum blocat. Doriți un card nou?"),
            ("customer", "Da, vă rog, la adresa de domiciliu."),
            ("agent", "Gata. Ajunge în 3-5 zile lucrătoare. Mai pot ajuta cu ceva?"),
            ("customer", "Nu, mulțumesc frumos."),
        ],
    ),
    "fraud_dispute": (
        [
            ("agent", "Salt Bank, how can I help you today?"),
            ("customer", "There are two payments I didn't make, to some website, 120 euros each."),
            ("agent", "Let's check that. I see two transactions last night flagged as unusual."),
            ("customer", "I never authorized those. I want my money back."),
            ("agent", "I'm opening a fraud dispute now and blocking the card as a precaution."),
            ("customer", "How long does the refund take?"),
            ("agent", "Provisional credit within 2 days, final decision within 10. You'll get an SMS."),
            ("customer", "Okay, thanks."),
        ],
        [
            ("agent", "Salt Bank, cu ce vă pot ajuta astăzi?"),
            ("customer", "Sunt două plăți pe care nu le-am făcut, către un site, câte 120 de euro."),
            ("agent", "Verific imediat. Văd două tranzacții de aseară marcate ca neobișnuite."),
            ("customer", "Nu le-am autorizat. Vreau banii înapoi."),
            ("agent", "Deschid acum o sesizare de fraudă și blochez cardul din precauție."),
            ("customer", "Cât durează rambursarea?"),
            ("agent", "Credit provizoriu în 2 zile, decizie finală în 10. Veți primi un SMS."),
            ("customer", "Bine, mulțumesc."),
        ],
    ),
    "loan_inquiry": (
        [
            ("agent", "Good morning, Salt Bank."),
            ("customer", "I'd like to know if I qualify for a personal loan of 10,000 euros."),
            ("agent", "I can do a soft check. What's the purpose and your monthly income?"),
            ("customer", "Home renovation, and I earn about 2,500 a month."),
            ("agent", "Based on that you'd likely qualify. I'll send a pre-offer to your app."),
            ("customer", "What interest rate roughly?"),
            ("agent", "Indicatively around 8.9% APR, subject to full assessment."),
            ("customer", "Great, I'll review it in the app."),
        ],
        [
            ("agent", "Bună dimineața, Salt Bank."),
            ("customer", "Aș vrea să știu dacă mă calific pentru un credit de 10.000 de euro."),
            ("agent", "Pot face o verificare preliminară. Care e scopul și venitul lunar?"),
            ("customer", "Renovarea casei, câștig aproximativ 2.500 pe lună."),
            ("agent", "Pe baza asta probabil vă calificați. Trimit o pre-ofertă în aplicație."),
            ("customer", "Aproximativ ce dobândă?"),
            ("agent", "Orientativ în jur de 8,9% DAE, sub rezerva evaluării complete."),
            ("customer", "Perfect, o verific în aplicație."),
        ],
    ),
    "app_technical": (
        [
            ("agent", "Salt Bank support, how can I help?"),
            ("customer", "The app won't let me log in, it says error 403."),
            ("agent", "Let's fix that. Have you updated to the latest version?"),
            ("customer", "I think so, but it still fails."),
            ("agent", "Please reinstall the app and log in with your phone number; I'll reset the session."),
            ("customer", "Okay... yes, it works now."),
            ("agent", "Great. I'll log this as a resolved technical issue."),
            ("customer", "Thanks for the quick help."),
        ],
        [
            ("agent", "Salt Bank suport, cu ce vă ajut?"),
            ("customer", "Aplicația nu mă lasă să mă loghez, îmi dă eroarea 403."),
            ("agent", "Rezolvăm. Ați actualizat la ultima versiune?"),
            ("customer", "Cred că da, dar tot nu merge."),
            ("agent", "Reinstalați aplicația și logați-vă cu numărul de telefon; resetez sesiunea."),
            ("customer", "Bine... da, acum funcționează."),
            ("agent", "Perfect. Notez ca problemă tehnică rezolvată."),
            ("customer", "Mulțumesc pentru ajutorul rapid."),
        ],
    ),
    "account_closure": (
        [
            ("agent", "Salt Bank, how may I assist?"),
            ("customer", "I want to close my account, I'm switching banks."),
            ("agent", "I'm sorry to hear that. May I ask the reason?"),
            ("customer", "Too many fees on transfers."),
            ("agent", "Understood. I can waive next month's fees if you'd like to stay."),
            ("customer", "No, I've decided. Please proceed."),
            ("agent", "I'll start the closure and transfer the balance to your listed IBAN."),
            ("customer", "Thank you."),
        ],
        [
            ("agent", "Salt Bank, cu ce vă pot ajuta?"),
            ("customer", "Vreau să îmi închid contul, schimb banca."),
            ("agent", "Îmi pare rău. Pot întreba motivul?"),
            ("customer", "Prea multe comisioane la transferuri."),
            ("agent", "Înțeleg. Pot anula comisioanele lunii viitoare dacă doriți să rămâneți."),
            ("customer", "Nu, m-am decis. Vă rog continuați."),
            ("agent", "Încep închiderea și transfer soldul către IBAN-ul înregistrat."),
            ("customer", "Mulțumesc."),
        ],
    ),
}

NAMES = ["Ana M.", "Radu P.", "Ioana T.", "Mihai D.", "Elena S.", "George V.", "Larisa N."]
SENTIMENTS = {"card_lost": "neutral", "fraud_dispute": "negative", "loan_inquiry": "positive",
              "app_technical": "neutral", "account_closure": "negative"}

# --- Realistic distributions (NOT uniform filler) ---------------------------
# Weights are chosen to reflect a real Romanian retail-bank support line, and
# they match the shape of the committed 40-call dataset in ./synthetic/.
#
# Category mix — lost/stolen cards dominate a card-issuer support line, tech and
# closures are rarer:
CATEGORY_WEIGHTS = {
    "card_lost":       0.325,   # most common contact reason
    "fraud_dispute":   0.175,
    "loan_inquiry":    0.175,
    "account_closure": 0.175,
    "app_technical":   0.150,   # least common
}
# Language balance — Salt Bank is a Romanian bank, so calls skew Romanian, with
# a meaningful English minority (expats / non-native speakers):
LANGUAGE_WEIGHTS = {"ro": 0.70, "en": 0.30}
# Sentiment is a deterministic property of the scenario (see SENTIMENTS), which
# yields a realistic skew: mostly neutral/negative with fewer clearly-positive
# calls — people rarely phone support when everything is fine.
#
# Call duration varies by category — fraud and loans run longer than a quick
# card block or login fix (mean seconds, lognormal-ish via gauss, clamped):
CATEGORY_DURATION = {
    "card_lost":       (150, 60),
    "fraud_dispute":   (300, 90),
    "loan_inquiry":    (300, 80),
    "account_closure": (220, 70),
    "app_technical":   (180, 60),
}


def weighted_choice(weights: dict[str, float]) -> str:
    """Sample one key from a {value: weight} mapping."""
    keys = list(weights)
    return random.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def render_transcript(category: str, lang: str) -> str:
    en, ro = SCENARIOS[category]
    turns = en if lang == "en" else ro
    name = random.choice(NAMES)
    lines = []
    for speaker, text in turns:
        lines.append(f"{speaker.upper()}: {text.format(name=name)}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="number of synthetic calls")
    ap.add_argument("--audio", action="store_true", help="also render TTS .wav files (needs pyttsx3)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    OUT.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS.mkdir(parents=True, exist_ok=True)

    tts = None
    if args.audio:
        try:
            import pyttsx3  # offline, no API key
            tts = pyttsx3.init()
        except Exception as e:  # pragma: no cover
            print(f"[warn] pyttsx3 unavailable ({e}); writing transcripts only.")

    base_time = datetime(2026, 9, 1, 9, 0, 0)
    meta_path = OUT / "calls_metadata.jsonl"

    from collections import Counter
    cat_counts: Counter[str] = Counter()
    lang_counts: Counter[str] = Counter()
    sent_counts: Counter[str] = Counter()

    with meta_path.open("w", encoding="utf-8") as mf:
        for i in range(args.n):
            call_id = f"CALL-{uuid.uuid4().hex[:10]}"
            # Weighted sampling → realistic category mix & language balance
            # (not uniform random.choice), with sentiment derived per scenario.
            category = weighted_choice(CATEGORY_WEIGHTS)
            lang = weighted_choice(LANGUAGE_WEIGHTS)
            mu, sigma = CATEGORY_DURATION[category]
            duration = max(60, min(600, int(random.gauss(mu, sigma))))
            ts = base_time + timedelta(minutes=random.randint(0, 20 * 24 * 60))
            transcript = render_transcript(category, lang)
            (TRANSCRIPTS / f"{call_id}.txt").write_text(transcript, encoding="utf-8")

            row = {
                "call_id": call_id,
                "agent": random.choice(AGENTS),
                "from_number": f"+407{random.randint(10_000_000, 99_999_999)}",
                "to_number": "+40316300000",
                "language": lang,
                "duration_seconds": duration,
                "started_at": ts.isoformat(),
                "expected_category": category,          # ground-truth label for eval
                "expected_sentiment": SENTIMENTS[category],
                "recording_uri": f"data/synthetic/transcripts/{call_id}.txt",
                "source": "synthetic",
            }
            mf.write(json.dumps(row, ensure_ascii=False) + "\n")
            cat_counts[category] += 1
            lang_counts[lang] += 1
            sent_counts[SENTIMENTS[category]] += 1

            if tts is not None:
                wav = OUT / "audio" / f"{call_id}.wav"
                wav.parent.mkdir(exist_ok=True)
                tts.save_to_file(transcript, str(wav))
        if tts is not None:
            tts.runAndWait()

    print(f"Wrote {args.n} synthetic calls → {meta_path}")
    print(f"Transcripts → {TRANSCRIPTS}")
    # Print realized distributions so the shaping is visible, not assumed.
    def _pct(counter):
        return ", ".join(f"{k} {v} ({v/args.n:.0%})"
                         for k, v in sorted(counter.items(), key=lambda x: -x[1]))
    print("\nRealized distributions (should reflect the weighted, non-uniform config):")
    print(f"  category : {_pct(cat_counts)}")
    print(f"  language : {_pct(lang_counts)}")
    print(f"  sentiment: {_pct(sent_counts)}")


if __name__ == "__main__":
    main()
