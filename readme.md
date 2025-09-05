Documentazione del Gioco di Avventura D&D
Questa documentazione descrive le specifiche tecniche e le regole di base del gioco di avventura testuale ispirato a Dungeons & Dragons.

1. Regole di Gioco
Punti Ferita (HP): L'eroe inizia l'avventura con 20 HP massimi. Se gli HP scendono a 0 o meno, il gioco termina e il giocatore perde.

Mostri: I mostri hanno un valore fisso di 10 HP. Una volta che i loro HP raggiungono 0 o meno, il mostro viene sconfitto.

Turni Massimi: L'avventura ha una durata massima di 12 scene. Raggiunto questo limite, il giocatore vince automaticamente la missione.

Combattimento: Il combattimento si basa su un tiro di dadi simulato (D20).

Sia l'eroe che il mostro "tirano" un D20.

Se il tiro dell'eroe è maggiore o uguale a quello del mostro, l'eroe infligge un danno pari alla differenza tra i due tiri.

Se il tiro del mostro è maggiore, il mostro infligge un danno pari alla differenza tra i due tiri.

Un tiro di 20 (critico) infligge un danno bonus aggiuntivo (5 + un tiro casuale da 1 a 4).

2. Funzionalità e Integrazioni
Generazione di Scenari: Il gioco utilizza il modello di linguaggio Llama 3.1 8B tramite il server Ollama per generare scenari, mostri e opzioni di scelta in tempo reale.

Generazione di Immagini: Per ogni nuovo scenario, l'applicazione si connette al server ComfyUI per creare un'immagine illustrativa basata sulla descrizione della scena.

Modello SD: playground-v2.5-1024px-aesthetic.fp16.safetensors

Dimensioni: L'immagine viene generata con una risoluzione di 512x512 pixel.

Sistema di Parsing: Il codice analizza l'output del modello AI per estrarre la descrizione della scena, il nome del mostro e le opzioni di scelta, gestendo autonomamente le azioni di combattimento. La logica è stata affinata per garantire la coerenza tra le opzioni e l'effettiva presenza di un mostro.

3. Struttura del Codice
Il file principale app.py contiene la logica del gioco e le API Flask:

generate_single_scenario(): Contatta il server Ollama per ottenere un testo generato.

generate_and_save_image(): Comunica con ComfyUI per creare un'immagine e salvarla nella cartella static.

handle_combat(): Contiene la logica del sistema di combattimento a dadi.

check_death() e check_victory(): Controllano le condizioni di fine gioco.

parse_game_response(): Estrae i dati rilevanti dal testo generato da Ollama.

start_adventure() e continue_adventure(): Gestiscono il flusso dell'avventura, lo stato della sessione e le risposte al giocatore.