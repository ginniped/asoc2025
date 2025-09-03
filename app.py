import requests
import json
import os
import re
from flask import Flask, render_template, request, jsonify, session
from comfy_client import ComfyUIClient

# --- Configurazione dei server ---
OLLAMA_SERVER_URL = "http://192.168.1.115:11434"
COMFYUI_SERVER_ADDRESS = "192.168.1.115:8188"
MODEL_NAME = "playground-v2.5-1024px-aesthetic.fp16.safetensors"

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
            steps=25,
            cfg=4.5,
        )
        
        if not generated_images:
            print("❌ Generazione immagine fallita: la chiamata ha restituito 0 immagini.")
            return None
        
        static_dir = os.path.join(app.root_path, 'static')
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)

        safe_title = re.sub(r'[^\w\s-]', '', title)
        safe_title = safe_title.replace(' ', '_')
        image_filename = f"{safe_title[:50]}.png"
        image_path = os.path.join(static_dir, image_filename)
        
        generated_images[0].save(image_path)
        
        print(f"✅ Immagine generata e salvata con successo in: {image_path}")
        return f"/static/{image_filename}"

    except Exception as e:
        print(f"🚨 Errore durante la generazione dell'immagine con ComfyUI: {e}")
        return None

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
    session['inventory'] = []
    
    start_prompt = f"""
Inizia un'avventura a scelte multiple in stile D&D basata su: '{title}'. 
Presenta la situazione iniziale e offri 3 opzioni numerate per il giocatore.
Usa ESATTAMENTE questo formato per la tua risposta:

SCENA:
[Descrivi qui la situazione iniziale in modo dettagliato]

OGGETTO:
[Nome dell'oggetto collezionabile, uno per scena. Lascia vuoto se non ce ne sono.]

SCELTE:
1. [Prima opzione]
2. [Seconda opzione]
3. [Terza opzione]
"""
    game_text = generate_single_scenario(start_prompt)
    scene, item, choices = parse_game_response(game_text)
    
    if item:
        session['found_item'] = item
        scene = f"Hai trovato un oggetto: '{item}'. Cosa vuoi fare?"
        choices = ["Raccogli l'oggetto", "Lascia l'oggetto dove si trova"]
    
    session['history'].append({'scene': scene, 'choices': choices})
    
    return render_template('game.html', title=title, scene=scene, choices=choices, inventory=session['inventory'])

@app.route('/continue_adventure', methods=['POST'])
def continue_adventure():
    data = request.json
    choice_made = data.get('choice')
    
    title = session.get('adventure_title')
    history = session.get('history', [])
    current_inventory = session.get('inventory', [])
    
    # Logica per la modalità di scambio di oggetti
    if "swap-mode" in session:
        item_to_remove = choice_made
        new_item = session['new_item']
        
        if item_to_remove != "Scarta il nuovo oggetto":
            current_inventory.remove(item_to_remove)
            current_inventory.append(new_item)
        
        del session['swap-mode']
        del session['new_item']
        
        next_prompt = f"""
        Dopo lo scambio, il giocatore ha proseguito l'avventura. L'inventario è ora: {', '.join(current_inventory)}.
        Continua la narrazione con una nuova scena e 3 opzioni.
        
        SCENA:
        [Descrivi qui la nuova situazione]
        
        OGGETTO:
        [Nome di un nuovo oggetto, se presente. Lascia vuoto se non ce ne sono.]
        
        SCELTE:
        1. [Prima opzione]
        2. [Seconda opzione]
        3. [Terza opzione]
        """
        game_text = generate_single_scenario(next_prompt)
        scene, item, choices = parse_game_response(game_text)
    
    # Nuova logica per la scelta di un oggetto trovato
    elif "found_item" in session:
        item = session['found_item']
        
        if choice_made == "Raccogli l'oggetto":
            if len(current_inventory) >= 10:
                session['swap-mode'] = True
                session['new_item'] = item
                
                scene = f"Hai trovato un nuovo oggetto: '{item}', ma il tuo inventario è pieno. Scegli cosa scartare per prenderlo o scartalo."
                choices = current_inventory + ["Scarta il nuovo oggetto"]
            else:
                current_inventory.append(item)
                # Genera nuova scena che continua dopo la raccolta
                next_prompt = f"""
                Il giocatore ha raccolto '{item}'. L'inventario è ora: {', '.join(current_inventory)}.
                Continua la narrazione con una nuova scena e 3 opzioni.
                SCENA:
                [Descrivi qui la nuova situazione]
                OGGETTO:
                [Nome di un nuovo oggetto, se presente. Lascia vuoto se non ce ne sono.]
                SCELTE:
                1. [Prima opzione]
                2. [Seconda opzione]
                3. [Terza opzione]
                """
                game_text = generate_single_scenario(next_prompt)
                scene, next_item, choices = parse_game_response(game_text)
                if next_item:
                    # In teoria potremmo avere due oggetti di fila, ma la logica è per uno per volta.
                    # Questa è una semplificazione per evitare un loop infinito.
                    # Se il modello ne suggerisce un altro, lo ignoriamo per ora.
                    pass
        
        del session['found_item']
        
        # Se il giocatore ha scelto di non raccogliere, continuiamo la storia come se nulla fosse
        if choice_made == "Lascia l'oggetto dove si trova":
            story_history = ""
            for entry in history:
                story_history += f"SCENA:\n{entry['scene']}\n"
                story_history += "SCELTE:\n" + "\n".join(entry['choices']) + "\n\n"
                
            next_prompt = f"""
            Basato sulla seguente cronologia dell'avventura '{title}':
            {story_history}

            Il giocatore ha deciso di non raccogliere l'oggetto.
            Continua la narrazione con una nuova scena e offri 3 nuove opzioni.
            
            SCENA:
            [Descrivi qui la nuova situazione in modo dettagliato]

            OGGETTO:
            [Nome dell'oggetto collezionabile, uno per scena. Lascia vuoto se non ce ne sono.]

            SCELTE:
            1. [Prima opzione]
            2. [Seconda opzione]
            3. [Terza opzione]
            """
            game_text = generate_single_scenario(next_prompt)
            scene, item, choices = parse_game_response(game_text)
            if item:
                session['found_item'] = item
                scene = f"Hai trovato un oggetto: '{item}'. Cosa vuoi fare?"
                choices = ["Raccogli l'oggetto", "Lascia l'oggetto dove si trova"]
    
    # Logica normale per proseguire la storia
    else:
        story_history = ""
        for entry in history:
            story_history += f"SCENA:\n{entry['scene']}\n"
            story_history += "SCELTE:\n" + "\n".join(entry['choices']) + "\n\n"
            
        inventory_prompt = f"Inventario attuale: {', '.join(current_inventory)}" if current_inventory else "Inventario attuale: vuoto"
        
        next_prompt = f"""
        Basato sulla seguente cronologia dell'avventura '{title}':
        {story_history}

        {inventory_prompt}

        Il giocatore ha appena scelto: '{choice_made}'.
        Continua la narrazione con una nuova scena e offri 3 nuove opzioni.
        Puoi menzionare un oggetto collezionabile nella scena.
        Usa ESATTAMENTE questo formato per la tua risposta:

        SCENA:
        [Descrivi qui la nuova situazione in modo dettagliato]

        OGGETTO:
        [Nome dell'oggetto collezionabile, uno per scena. Lascia vuoto se non ce ne sono.]

        SCELTE:
        1. [Prima opzione]
        2. [Seconda opzione]
        3. [Terza opzione]
        """
        game_text = generate_single_scenario(next_prompt)
        scene, item, choices = parse_game_response(game_text)
        
        if item:
            session['found_item'] = item
            scene = f"Hai trovato un oggetto: '{item}'. Cosa vuoi fare?"
            choices = ["Raccogli l'oggetto", "Lascia l'oggetto dove si trova"]

    history.append({'scene': scene, 'choices': choices})
    session['history'] = history
    session['inventory'] = current_inventory
    
    return jsonify({"scene": scene, "choices": choices, "inventory": current_inventory})

def parse_game_response(text):
    scene_match = re.search(r'SCENA:\s*([\s\S]*?)\s*(OGGETTO:|SCELTE:)', text, re.DOTALL)
    item_match = re.search(r'OGGETTO:\s*([\s\S]*?)\s*SCELTE:', text, re.DOTALL)
    choices_match = re.search(r'SCELTE:\s*([\s\S]*)', text, re.DOTALL)

    scene = "Descrizione non trovata. Riprova. Probabilmente Ollama si è interrotto."
    item = None
    choices = ["Scelte non trovate. Riprova."]
    
    if scene_match:
        scene = scene_match.group(1).strip()
    
    if item_match:
        item_text = item_match.group(1).strip()
        if item_text and item_text.lower() not in ["vuoto", "nessuno", "nessun oggetto"]:
            item = item_text

    if choices_match:
        choices_text = choices_match.group(1).strip()
        choices = [c.strip() for c in choices_text.split('\n') if c.strip()]
        
    if not choices:
        choices = ["Scelte non trovate. Riprova."]

    return scene, item, choices

if __name__ == '__main__':
    app.run(debug=True)