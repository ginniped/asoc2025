import requests
import json
import os
import re
from flask import Flask, render_template, request, jsonify
from comfy_client import ComfyUIClient

# --- Configurazione dei server ---
OLLAMA_SERVER_URL = "http://192.168.1.115:11434"
COMFYUI_SERVER_ADDRESS = "192.168.1.115:8188"
MODEL_NAME = "playground-v2.5-1024px-aesthetic.fp16.safetensors"

# Inizializza l'applicazione Flask e il client di ComfyUI
app = Flask(__name__)
comfy_client = ComfyUIClient(COMFYUI_SERVER_ADDRESS)

# Funzione per generare un singolo scenario con Ollama
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

# Rotta principale che renderizza la pagina web
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

# Nota: ho modificato la rotta in <path:title> per gestire titoli con caratteri speciali
@app.route('/adventure/<path:title>')
def start_adventure(title):
    # Prompt per il gioco iniziale, con istruzioni chiare per Ollama
    start_prompt = f"""
Inizia un'avventura a scelte multiple in stile D&D basata su: '{title}'. 
Presenta la situazione iniziale e offri 3 opzioni numerate per il giocatore.
Usa ESATTAMENTE questo formato per la tua risposta:

SCENA:
[Descrivi qui la situazione iniziale in modo dettagliato]

SCELTE:
1. [Prima opzione]
2. [Seconda opzione]
3. [Terza opzione]
"""
    game_text = generate_single_scenario(start_prompt)
    scene, choices = parse_game_response(game_text)
    
    return render_template('game.html', title=title, scene=scene, choices=choices)

@app.route('/continue_adventure', methods=['POST'])
def continue_adventure():
    data = request.json
    title = data.get('title')
    choice_made = data.get('choice')

    # Prompt per continuare l'avventura
    next_prompt = f"""
Nell'avventura '{title}', il giocatore ha scelto: '{choice_made}'.
Continua la narrazione con una nuova scena e offri 3 nuove opzioni.
Usa ESATTAMENTE questo formato per la tua risposta:

SCENA:
[Descrivi qui la nuova situazione in modo dettagliato]

SCELTE:
1. [Prima opzione]
2. [Seconda opzione]
3. [Terza opzione]
"""
    game_text = generate_single_scenario(next_prompt)
    scene, choices = parse_game_response(game_text)
    
    return jsonify({"scene": scene, "choices": choices})

# Funzione per estrarre scena e scelte in modo robusto
def parse_game_response(text):
    scene_match = re.search(r'SCENA:\s*([\s\S]*?)\s*SCELTE:', text, re.DOTALL)
    choices_match = re.search(r'SCELTE:\s*([\s\S]*)', text, re.DOTALL)

    scene = "Descrizione non trovata. Riprova."
    choices = ["Scelte non trovate. Riprova."]

    if scene_match:
        scene = scene_match.group(1).strip()
    
    if choices_match:
        choices_text = choices_match.group(1).strip()
        choices = [c.strip() for c in choices_text.split('\n') if c.strip()]

    return scene, choices

if __name__ == '__main__':
    app.run(debug=True)