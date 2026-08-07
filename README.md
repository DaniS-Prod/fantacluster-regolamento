# Regolamento Fantacluster — sito statico

Il regolamento della lega pubblicato come **sito statico** su GitHub Pages, generato
da un unico file Markdown con uno script Python. Niente framework, niente npm,
niente build tool: solo [`mistune`](https://mistune.lepture.com/) + un template.

- **Sorgente**: [`src/regolamento-2026-27.md`](src/regolamento-2026-27.md) — la fonte di verità, in Markdown.
- **Output**: [`docs/index.html`](docs/index.html) — pagina unica autosufficiente, servita da Pages.
- **Riferimento**: [`originali/`](originali/) — i `.docx` di partenza, uno per stagione (solo consultazione, non usati dalla build).

## Caratteristiche della pagina

- **Mobile-first.** Indice laterale sticky su desktop, collassabile (bottone ☰) su mobile.
- **Ogni comma è ancorabile** con id nel formato `art-6-4` (e i sotto-commi `art-6-5-1`).
  L'icona 🔗 accanto al numero **copia negli appunti l'URL completo** del comma.
- **Ricerca testuale** client-side: filtra i commi mentre digiti (nessuna libreria esterna,
  accenti ignorati, più parole in AND).
- **Tabelle leggibili a 375px**: si riflettono automaticamente in *card* quelle larghe o con
  celle lunghe (Tabella A, B), le altre restano a scorrimento orizzontale.
- **Autosufficiente e offline**: CSS e JS sono inline, nessuna risorsa esterna → funziona
  anche **aperta in locale con doppio click**, senza server (il fallback da mandare in chat).
- `noindex` (contiene nomi e cognomi reali), tema chiaro/scuro automatico, nessun cookie/analytics.

## Requisiti

- Python 3 (testato con 3.14)
- `pip install mistune` (oppure `pip install -r requirements.txt`)

## Rigenerare il sito dopo una modifica al Markdown

1. Modifica [`src/regolamento-2026-27.md`](src/regolamento-2026-27.md).
2. Rilancia il generatore:

   ```bash
   python build.py
   ```

   Rigenera `docs/index.html`. La **data di «ultima modifica»** mostrata in testa viene
   presa dall'ultimo commit git che ha toccato `src/`; se ci sono modifiche non ancora
   committate usa la data odierna, così la data è corretta anche rigenerando prima di committare.
3. Committa sia il sorgente sia l'output:

   ```bash
   git add -A && git commit -m "Aggiorna regolamento"
   git push
   ```

GitHub Pages ripubblicherà da solo entro un minuto.

## Attivare GitHub Pages da `/docs` sul branch `main`

1. Crea il repository su GitHub e fai `git push` (vedi sotto).
2. Sul repo: **Settings → Pages**.
3. In **Build and deployment → Source** scegli **«Deploy from a branch»**.
4. In **Branch** seleziona **`main`** e la cartella **`/docs`**, poi **Save**.
5. Dopo qualche istante il sito è online su `https://<tuo-utente>.github.io/<nome-repo>/`.

Il sito resta sul dominio `github.io` (nessun `CNAME`, nessun dominio custom).

### Prima pubblicazione (push iniziale)

```bash
git remote add origin https://github.com/<tuo-utente>/<nome-repo>.git
git push -u origin main
```

## Configurazione (in cima a [`build.py`](build.py))

- `INCLUDI_FIRME` — default `False`. Il sorgente contiene la sezione «Sottoscrizioni»
  (le firme) per fedeltà all'originale, ma **non** viene pubblicata sul sito. Metti `True`
  per includerla.
- `SITE_URL` — se valorizzato con l'URL del sito Pages
  (es. `"https://tuo-utente.github.io/fantacluster-regolamento/"`), il tasto «copia link»
  produce sempre un link al sito pubblicato, **anche aprendo il file in locale**. Lascialo
  vuoto per usare l'indirizzo corrente della pagina.

## Formato del Markdown sorgente

| Elemento | Sintassi | Risultato |
|---|---|---|
| Titolo pagina | `# Regolamento … 2026-2027` | Titolo + stagione (anche da front matter `stagione:`) |
| Articolo | `## Art. 6 — Titolo {#art-6}` | Sezione numerata «Art. 6» |
| Comma | `### 6.4 {#art-6-4}` | Comma ancorabile `#art-6-4` |
| Sotto-comma | `#### 6.5.1 {#art-6-5-1}` | Sotto-punto ancorabile |
| Appendice | `## Titolo {#firme}` (id non `art-…`) | Sezione non numerata |
| Chiusura | `---` seguito dal testo | Motto centrato a fine pagina |
| Tabelle / liste / **grassetto** / *corsivo* / `<br>` | Markdown standard | Come da originale |

Gli `{#id}` espliciti sono usati come ancore così come sono; se un heading non ha id,
viene numerato automaticamente in base alla posizione.
