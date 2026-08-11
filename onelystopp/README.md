# onelystopp

Frontend for the onelystopp revision platform — question bank, PYQ mix, AI exams, answer marking, diagrams, interview practice, and progress tools.

## Design system

Matched to the Uxcel-inspired reference (`public/inspiration-uxcel.png`):

- Primary purple `#5b52f0`
- Plus Jakarta Sans
- Soft sidebar, rounded lesson cards, purple active borders, top utility bar

## Run

```bash
cd onelystopp
npm install
npm run dev
```

## Features (routed)

| Route | Feature |
| --- | --- |
| `/` | Home study path |
| `/question-bank` | Question bank |
| `/past-papers` | Past paper finder |
| `/pyq-mix` | PYQ mix generator |
| `/ai-exams` | AI-curated exams |
| `/theory` | Theory & tricks |
| `/revision` | Revision guide |
| `/marker` | Answer / Essay / Long Answer Marker (name follows subject) |
| `/diagrams` | Diagram generator |
| `/interview` | AI interview (STT/TTS UI) |
| `/tutor` | AI tutor |
| `/progress` | Progress tracker |
| `/memory` | A* memory |
| `/notes` | Sticky notes |

Subject and exam board selectors in the top bar drive dynamic copy (e.g. “exact OCR marking criteria”).
