import requests
import json
import os
import re
import random
from flask import Flask, render_template, request, jsonify, session
from comfy_client import ComfyUIClient

# --- Configurazione dei server ---
OLLAMA_SERVER_URL = "http://192.168.1.115:11434"
COMFYUI_SERVER_ADDRESS = "192.168.1.115:8188"
MODEL_NAME = "playground-v2.5-1024px-aesthetic.fp16.safetensors"
MAX_SCENES = 12
INITIAL_HP = 20
IMAGE_WIDTH = 512
IMAGE_HEIGHT = 512

# Inizializza l'applicazione Flask e il client di ComfyUI
app = Flask(__name__)
app.secret_key = 'la_tua_chiave_segreta_molto_difficile'

try:
    from comfy_client import ComfyUIClient
    comfy_client = ComfyUIClient(COMFYUI_SERVER_ADDRESS)
except ImportError:
    print("La libreria 'comfy_client' non è installata. Le funzionalità di generazione immagini non saranno disponibili.")
    comfy_client = None

def generate_single_scenario(prompt, model="llama3.1:8b"):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(f"{OLLAMA_SERVER_URL}/api/generate", data=json.dumps(payload), headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        data = response.json()
        return data.get("response", "Errore: 'response' non trovato nella risposta.")
    except requests.exceptions.RequestException as e:
        print(f"Errore nella richiesta a Ollama: {e}")
        return "Errore nella richiesta a Ollama."
    except json.JSONDecodeError as e:
        print(f"Errore nella decodifica JSON da Ollama: {e}")
        return "Errore nella decodifica JSON da Ollama."

def generate_and_save_image(title, ambientazione, trama):
    if not comfy_client:
        return None

    positive_prompt = f"Fantasy illustration of a D&D adventure: {title}. The setting is {ambientazione}. The quest involves: {trama}. High detail, cinematic lighting, dramatic atmosphere."
    negative_prompt = "(worst quality, low quality, normal quality), blurry, ugly, disfigured, watermark, text, signature, plain background"

    print(f"Tentativo di generazione immagine per: '{title}'")

    try:
        generated_images = comfy_client.generate_images(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            model_name=MODEL_NAME,
            width=IMAGE_WIDTH,
            height=IMAGE_HEIGHT,
            steps=18,
            cfg=4.0,
        )

        if not generated_images:
            print("❌ Generazione immagine fallita: la chiamata ha restituito 0 immagini.")
            return None

        static_dir = os.path.join(app.root_path, 'static')
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)

        # Pulizia robusta del titolo per evitare caratteri non validi nei nomi dei file
        safe_title = re.sub(r'[^\w\s-]', '', title)
        safe_title = re.sub(r'\s+', '_', safe_title).strip('_')
        image_filename = f"{safe_title[:50]}.png"
        image_path = os.path.join(static_dir, image_filename)
        
        generated_images[0].save(image_path)

        print(f"✅ Immagine generata e salvata con successo in: {image_path}")
        return f"/static/{image_filename}"

    except Exception as e:
        print(f"🚨 Errore durante la generazione dell'immagine con ComfyUI: {e}")
        return None

# Funzione per gestire il combattimento
def handle_combat():
    player_roll = random.randint(1, 20)
    monster_roll = random.randint(1, 20)

    player_hp = session.get('current_hp', INITIAL_HP)

    combat_log = []

    if player_roll >= monster_roll:
        damage = 0
        if player_roll > monster_roll:
            damage = player_roll - monster_roll
            if player_roll == 20:
                damage = 5 + random.randint(1, 4)
            combat_log.append(f"Hai attaccato! Il tuo D20 è {player_roll}, il mostro è {monster_roll}. Infliggi {damage} danni.")
            session['current_monster_hp'] -= damage
        else:
            combat_log.append(f"Pareggio! Il tuo D20 è {player_roll}, il mostro è {monster_roll}. Nessuno subisce danni.")
    else:
        damage = monster_roll - player_roll
        if monster_roll == 20:
            damage = 5 + random.randint(1, 4)
        combat_log.append(f"Il mostro ti ha attaccato! Il tuo D20 è {player_roll}, il mostro è {monster_roll}. Subisci {damage} danni.")
        player_hp -= damage

    session['current_hp'] = player_hp

    return combat_log

# Funzione per verificare la condizione di sconfitta
def check_death():
    return session.get('current_hp', 0) <= 0

# Funzione per verificare la condizione di vittoria
def check_victory():
    return session.get('current_scene_number', 0) >= MAX_SCENES

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_scenarios', methods=['POST'])
def generate_scenarios():
    base_prompt = """
Genera 3 scenari unici per un'avventura di Dungeons & Dragons in lingua italiana.
Ogni scenario deve essere formattato ESATTAMENTE come segue:

---SCENARIO---
Titolo: [Inserisci qui il titolo dello scenario]
Ambientazione: [Inserisci qui l'ambientazione]
Trama/Missione principale: [Inserisci qui la trama]
---END SCENARIO---

Non includere introduzioni, conclusioni o testo aggiuntivo. Non usare caratteri di formattazione come * o #.
"""

    generated_text = generate_single_scenario(base_prompt)
    cleaned_text = re.sub(r'[*#]', '', generated_text)
    cleaned_text = cleaned_text.replace("L&amp;#39;", "'")

    scenarios_data = []
    scenarios = cleaned_text.split("---SCENARIO---")
    if len(scenarios) > 1:
        scenarios = scenarios[1:]

    for scenario_text in scenarios:
        clean_scenario_text = scenario_text.split("---END SCENARIO---")[0].strip()
        title_match = re.search(r'Titolo:\s*(.*)', clean_scenario_text)
        ambientazione_match = re.search(r'Ambientazione:\s*(.*)', clean_scenario_text)
        trama_match = re.search(r'Trama/Missione principale:\s*(.*)', clean_scenario_text)

        title = title_match.group(1).strip() if title_match else "Titolo non trovato"
        ambientazione = ambientazione_match.group(1).strip() if ambientazione_match else "Ambientazione non trovata"
        trama = trama_match.group(1).strip() if trama_match else "Trama non trovata"

        image_url = generate_and_save_image(title, ambientazione, trama)

        scenarios_data.append({
            "title": title,
            "ambientazione": ambientazione,
            "trama": trama,
            "image_url": image_url
        })

    return render_template('results.html', scenarios=scenarios_data)

@app.route('/adventure/<path:title>')
def start_adventure(title):
    session.clear()
    session['adventure_title'] = title
    session['history'] = []
    session['current_hp'] = INITIAL_HP
    session['current_scene_number'] = 1
    session['monsters_encountered'] = []

    start_prompt = f"""
Sei il Game Master di un'avventura di Dungeons & Dragons.
L'avventura è basata su: '{title}'.
Descrivi la situazione iniziale. A volte, includi la possibilità di incontrare un mostro.
Le opzioni di scelta devono essere 3 e devono essere coerenti con la SCENA. Se incontri un mostro, aggiungi l'opzione "Attacca il mostro".
NON AGGIUNGERE TESTO AGGIUNTIVO DOPO L'ULTIMA SCELTA.
Usa ESATTAMENTE questo formato per la tua risposta:

SCENA:
[Descrivi qui la situazione iniziale in modo dettagliato]

MOSTRO:
[Nome del mostro, es. "Goblin". Lascia vuoto se non c'è.]

SCELTE:
1. [Prima opzione]
2. [Seconda opzione]
3. [Terza opzione]
"""
    game_text = generate_single_scenario(start_prompt)
    scene, monster, choices = parse_game_response(game_text)
    
    session['initial_scene'] = scene
    session['initial_choices'] = choices
    session['initial_title'] = title

    if monster:
        session['current_monster'] = monster
        session['current_monster_hp'] = 10

    session['history'].append({'scene': scene, 'choices': choices})

    return render_template('game.html', title=title, scene=scene, choices=choices, current_hp=session['current_hp'])

@app.route('/continue_adventure', methods=['POST'])
def continue_adventure():
    data = request.json
    choice_made = data.get('choice')

    if choice_made == "Ricomincia la stessa avventura":
        session.clear()
        session['adventure_title'] = session.get('initial_title')
        session['history'] = []
        session['current_hp'] = INITIAL_HP
        session['current_scene_number'] = 1
        scene = session.get('initial_scene')
        choices = session.get('initial_choices')
        session['history'].append({'scene': scene, 'choices': choices})
        return jsonify({"scene": scene, "choices": choices, "current_hp": INITIAL_HP})
    
    if choice_made == "Scegli una nuova avventura":
        session.clear()
        return jsonify({"redirect": "/"})

    # Nuova logica: se l'opzione contiene "attacca", entra in modalità combattimento
    if "attacca" in choice_made.lower():
        # Estrai il nome del mostro dall'opzione
        monster_name = "mostro"
        match = re.search(r'attacca\s+(il|lo|la|l\'|un|uno|una)\s+(.*)', choice_made.lower())
        if match:
            monster_name = match.group(2).strip().replace("!", "").replace(".", "")
        
        # Sostituisci il mostro della sessione con quello estratto
        session['current_monster'] = monster_name
        
        # Se non c'era un mostro, imposta gli HP di base per il combattimento
        if 'current_monster_hp' not in session:
            session['current_monster_hp'] = 10
        
        combat_log = handle_combat()
        monster = session['current_monster']
        monster_hp = session['current_monster_hp']

        # ***NUOVA POSIZIONE PER I CONTROLLI DI STATO***
        if check_death():
            return jsonify({"scene": "Sei morto! L'avventura è finita.", "choices": ["Ricomincia la stessa avventura", "Scegli una nuova avventura"], "current_hp": session['current_hp']})

        if monster_hp <= 0:
            del session['current_monster']
            del session['current_monster_hp']
            scene = f"Hai sconfitto il {monster}! {'. '.join(combat_log)} Cosa fai ora?"
            next_prompt = f"""
            Il giocatore ha sconfitto il {monster}. Continua la narrazione con una nuova scena e 3 opzioni.
            La descrizione della SCENA deve essere concisa ma dettagliata.
            NON AGGIUNGERE TESTO AGGIUNTIVO DOPO L'ULTIMA SCELTA.

            SCENA:
            [Descrivi qui la nuova situazione]

            MOSTRO:
            
            SCELTE:
            1. [Prima opzione]
            2. [Seconda opzione]
            3. [Terza opzione]
            """
            game_text = generate_single_scenario(next_prompt)
            new_scene, new_monster, choices = parse_game_response(game_text)
            scene += new_scene

        else:
            scene = f"Il combattimento continua! {'. '.join(combat_log)} Il {monster} ha {monster_hp} HP rimasti. Cosa fai?"
            choices = ["Attacca di nuovo", "Tenta di fuggire"]

        session['current_hp'] = session['current_hp']
    else:
        title = session.get('adventure_title')
        history = session.get('history', [])
        story_history = ""
        for entry in history:
            story_history += f"SCENA:\n{entry['scene']}\n"
            story_history += "SCELTE:\n" + "\n".join(entry['choices']) + "\n\n"

        next_prompt = f"""
        Basato sulla seguente cronologia dell'avventura '{title}':
        {story_history}

        Il giocatore ha appena scelto: '{choice_made}'.
        Continua la narrazione con una nuova scena e offri 3 nuove opzioni. A volte includi la possibilità di incontrare un mostro.
        Le opzioni di scelta devono essere coerenti con la SCENA.
        Se nella SCENA è presente un mostro, aggiungi l'opzione "Attacca il mostro".
        NON AGGIUNGERE TESTO AGGIUNTIVO DOPO L'ULTIMA SCELTA.
        Usa ESATTAMENTE questo formato per la tua risposta:

        SCENA:
        [Descrivi qui la nuova situazione in modo dettagliato]

        MOSTRO:
        [Nome del mostro, es. "Goblin". Lascia vuoto se non c'è.]

        SCELTE:
        1. [Prima opzione]
        2. [Seconda opzione]
        3. [Terza opzione]
        """
        game_text = generate_single_scenario(next_prompt)
        scene, monster, choices = parse_game_response(game_text)

        # Nuova logica: se il mostro non è presente, filtra le opzioni di attacco
        if not monster:
            choices = [c for c in choices if "attacca" not in c.lower()]
        
        session['current_scene_number'] += 1

    session['history'].append({'scene': scene, 'choices': choices})

    # Controllo di morte e vittoria dopo ogni mossa, indipendentemente dal tipo
    if check_death():
        return jsonify({"scene": "Sei morto! L'avventura è finita.", "choices": ["Ricomincia la stessa avventura", "Scegli una nuova avventura"], "current_hp": session['current_hp']})

    if check_victory():
        current_hp = session.get('current_hp')
        return jsonify({"scene": "Hai completato la missione! L'avventura è finita.", "choices": ["Ricomincia la stessa avventura", "Scegli una nuova avventura"], "current_hp": current_hp})

    return jsonify({"scene": scene, "choices": choices, "current_hp": session['current_hp']})

def parse_game_response(text):
    # Ripulisce il testo da codici HTML non validi
    text = text.replace("L&amp;#39;", "'")
    
    scene_match = re.search(r'SCENA:\s*([\s\S]*?)\s*(MOSTRO:|SCELTE:)', text, re.DOTALL)
    monster_match = re.search(r'MOSTRO:\s*([\s\S]*?)\s*SCELTE:', text, re.DOTALL)
    choices_match = re.search(r'SCELTE:\s*([\s\S]*)', text, re.DOTALL)

    scene = "Descrizione non trovata. Riprova. Probabilmente Ollama si è interrotto."
    monster = None
    choices = ["Scelte non trovate. Riprova."]

    if scene_match:
        scene = scene_match.group(1).strip()

    if monster_match:
        monster_text = monster_match.group(1).strip()
        if monster_text and monster_text.lower() not in ["vuoto", "nessuno", "nessun mostro", "nessuno."]:
            monster = monster_text

    if choices_match:
        choices_text = choices_match.group(1).strip()
        choices = [c.strip() for c in choices_text.split('\n') if c.strip()]

    if not choices:
        choices = ["Scelte non trovate. Riprova."]
    
    # Rimuovi l'opzione di default "Attacca il mostro" se non è presente nel testo generato
    # e se non ci sono altre opzioni di attacco generate dal modello.
    if monster is None and "attacca il mostro" in [c.lower() for c in choices]:
        choices.remove("Attacca il mostro")

    return scene, monster, choices

if __name__ == '__main__':
    app.run(debug=True)