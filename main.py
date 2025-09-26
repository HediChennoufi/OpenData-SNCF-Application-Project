import folium
from folium import Popup
from flask import Flask, render_template, request, jsonify
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import pandas as pd
from datetime import datetime
import requests

test = Flask(__name__)

images_destinations = {
    "PARIS":
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/Paris_-_The_Eiffel_Tower_in_spring_-_2307.jpg/960px-Paris_-_The_Eiffel_Tower_in_spring_-_2307.jpg?20130724180149",
    "MARSEILLE ST CHARLES":
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/eb/Marseille-Vieux_port_vers_1900-2.jpg/960px-Marseille-Vieux_port_vers_1900-2.jpg?20101009145207",
    "LYON":
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/49/Quai_Fulchiron_in_Lyon_%281%29.jpg/960px-Quai_Fulchiron_in_Lyon_%281%29.jpg?20250719142928",
    "TOULOUSE MATABIAU":
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Toulouse_Capitole_Night_Wikimedia_Commons.jpg/640px-Toulouse_Capitole_Night_Wikimedia_Commons.jpg",
    "NICE VILLE":
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/62/Nice_from_Castle_Hill_01.jpg/640px-Nice_from_Castle_Hill_01.jpg",
    "MONTPELLIER SAINT ROCH":
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Montpellier%2C_France_-_panoramio_%282%29.jpg/640px-Montpellier%2C_France_-_panoramio_%282%29.jpg",
    "STRASBOURG":
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Gerwerstub_1572%2C_maison_des_tanneurs%2C_Strasbourg_%282014%29.jpg/640px-Gerwerstub_1572%2C_maison_des_tanneurs%2C_Strasbourg_%282014%29.jpg",
    "BORDEAUX":
    "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Bordeaux%2C_France_%287363127682%29.jpg/640px-Bordeaux%2C_France_%287363127682%29.jpg",
    "LILLE":
    "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f8/Lille_vue_gd_place.JPG/640px-Lille_vue_gd_place.JPG"
}


@test.route('/', methods=['GET', 'POST'])
def index():
    carte_html = None
    message = ""
    if request.method == 'POST':
        adresse = request.form.get('adresse')
        temps_trajet = int(request.form.get('temps_trajet'))
        heure_depart = int(request.form.get('heure_depart'))
        heure_retour_max = int(request.form.get('heure_retour'))
        date_str = request.form.get('date')
        abonnement_max = request.form.get('abonnement_max') == 'oui'
        geolocator = Nominatim(user_agent="mon_projet")
        location = geolocator.geocode(adresse, country_codes="fr")
        # Lire le fichier csv
        df = pd.read_csv('https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/tgvmax/exports/csv?lang=fr&timezone=Europe%2FBerlin&use_labels=true&delimiter=%3B', sep=';')
        df = df[~df['ENTITY'].str.contains('AUTOCAR SNCF', na=False)]
        df = df[~df['Axe'].str.contains('INTERNATIONAL', na=False)]
        df = df.replace(to_replace="PARIS (intramuros)",
                        value="PARIS",
                        regex=False)
        df = df.replace(to_replace="LYON (intramuros)",
                        value="LYON",
                        regex=False)
        df = df.replace(to_replace="LILLE (intramuros)",
                        value="LILLE",
                        regex=False)
        #conversions
        df['Heure_arrivee'] = pd.to_datetime(df['Heure_arrivee'],
                                             format='%H:%M')
        df['Heure_depart'] = pd.to_datetime(df['Heure_depart'], format='%H:%M')
        df['temps'] = abs(df['Heure_arrivee'] - df['Heure_depart'])
        # Filtre trajets
        df_time = df[(df['temps'] < pd.Timedelta(hours=temps_trajet))
                     & (df['Heure_depart'].dt.hour >= heure_depart)
                     & (df['Origine'] == adresse) & (df['DATE'] == date_str)]

        if abonnement_max == True:
            df_time = df_time[
                df_time['Disponibilité de places MAX JEUNE et MAX SENIOR'] ==
                'OUI']

        trajets_valides = []
        for idx, row in df_time.iterrows(
        ):  #iterrows convoie couple (index, row(serie d'elems))
            destination = row['Destination']  #extrait la destination de l'allé
            heure_arrivee_aller = row[
                'Heure_arrivee']  #l'heure d'arrivee de l'allé
            df_retour = df[(df['Origine'] == destination) &
                           (df['Destination'] == adresse) &
                           (df['DATE']
                            == date_str)]  #trajets retour possibles le mm jour
            retour_possible = False
            for _, ret_row in df_retour.iterrows():
                if (ret_row['Heure_depart'] > heure_arrivee_aller) and (
                        ret_row['Heure_depart'].hour <= heure_retour_max):
                    retour_possible = True
                    break
            if retour_possible:
                trajets_valides.append(row)
        df_tout = pd.DataFrame(trajets_valides)
        # Calcul heure max retour par destination
        heure_retour_max_par_destination = {}
        for destination in df_tout['Destination'].unique():
            df_retour = df[(df['Origine'] == destination)
                           & (df['Destination'] == adresse) &
                           (df['DATE'] == date_str)]
            heure_max_retour = None
            for _, ret_row in df_retour.iterrows():
                heure_depart_retour = ret_row['Heure_depart'].time()
                limite_retour = datetime.strptime(f"{heure_retour_max}:59",
                                                  "%H:%M").time()
                if heure_depart_retour <= limite_retour:
                    if heure_max_retour is None or heure_depart_retour > heure_max_retour:
                        heure_max_retour = heure_depart_retour
            heure_retour_max_par_destination[destination] = heure_max_retour
        df_tout['heure_retour_max'] = df_tout['Destination'].map(
            heure_retour_max_par_destination)  #créee nvlle colonne
        # Rassembler toutes les heures départ aller par destination
        infos_par_destination = {}
        for destination in df_tout['Destination'].unique():
            heures_aller = df_tout[df_tout['Destination'] == destination][
                'Heure_depart'].dt.time.tolist()
            heures_aller = sorted(heures_aller,
                                  key=lambda h: (h.hour, h.minute))
            # Récupérer l'heure de retour max pour cette destination
            heure_retour_max_val = df_tout.loc[df_tout['Destination'] ==
                                               destination,
                                               'heure_retour_max'].iloc[0]
            infos_par_destination[destination] = {
                'heures_aller': heures_aller,
                'heure_retour_max': heure_retour_max_val
            }
            print(
                f"Destination : {destination} | Heures départ aller : {', '.join(str(h) for h in heures_aller)} | "
                f"Dernier retour possible à : {heure_retour_max_val if heure_retour_max_val else 'Aucun'}"
            )
        if location:
            carte = folium.Map(
                location=[location.latitude, location.longitude],
                zoom_start=10)
            folium.Marker([location.latitude, location.longitude],
                          popup=adresse,
                          icon=folium.Icon(color='blue')).add_to(carte)
            df_unique_dest = df_tout.drop_duplicates(
                subset=['Destination'])  # un seul marker par destinatio
            for j in range(len(df_unique_dest)):
                destination = df_unique_dest.iloc[j]['Destination']
                location_dest = geolocator.geocode(destination,
                                                   country_codes="fr",
                                                   timeout=25)
                if location_dest:
                    donnees = infos_par_destination[destination]
                    activite = get_top_attraction(location_dest.latitude,
                                                  location_dest.longitude,
                                                  radius=2000)
                    duree_moyenne_min = int(
                        df_tout[df_tout['Destination'] == destination]
                        ['temps'].mean().total_seconds() // 60)
                    image_url = images_destinations.get(
                        destination,
                        "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSPikddtu5wxj32FRFwZyzFkxfXjy-D9An1mA&s"
                    )

                    popup_html = f'''
                    <div style="
                        width: 350px; 
                        max-height: 280px; 
                        overflow-y: auto; 
                        font-family: Arial, sans-serif;
                        border-radius: 12px; 
                        box-shadow: 0 4px 15px rgba(0,0,0,0.2); 
                        background: #f9f9f9; 
                        color: #333;
                        ">
                        <img src="{image_url}" alt="Image {destination}" style="
                            width: 100%; 
                            height: 160px; 
                            object-fit: cover; 
                            border-top-left-radius: 12px; 
                            border-top-right-radius: 12px;">
                        <div style="padding: 12px 15px;">
                            <h3 style="margin-top: 0; margin-bottom: 10px; color: #355c7d;">{destination}</h3>
                            <p style="margin: 5px 0; font-size: 0.9rem;"><strong>Heures départ aller :</strong><br>{", ".join(str(h) for h in donnees['heures_aller'])}</p>
                            <p style="margin: 5px 0; font-size: 0.9rem;"><strong>Durée moyenne du trajet :</strong> {duree_moyenne_min} minutes</p>
                            <p style="margin: 5px 0; font-size: 0.9rem;"><strong>Dernière heure de retour :</strong> {donnees['heure_retour_max'] if donnees['heure_retour_max'] else 'N/A'}</p>
                            <p style="margin: 5px 0; font-size: 0.9rem;"><strong>Commerces :</strong> {compter_shops(location_dest.latitude, location_dest.longitude, 2000, "shop")}</p>
                            <p style="margin: 5px 0; font-size: 0.9rem;"><strong>Activités :</strong> {compter_shops(location_dest.latitude, location_dest.longitude, 2000, "tourism")}</p>
                            <p style="margin: 5px 0; font-size: 0.9rem;"><strong>Consommation CO<sub>2</sub> voiture :</strong> {round(geodesic((location.latitude,location.longitude), (location_dest.latitude,location_dest.longitude)).km*108/1000,3)} kg</p>
                            <p style="margin: 5px 0; font-size: 0.9rem;"><strong>Consommation CO<sub>2</sub> train :</strong> {round(geodesic((location.latitude,location.longitude), (location_dest.latitude,location_dest.longitude)).km*5.5/1000,3)} kg</p>
                            <p style="margin: 5px 0; font-size: 0.9rem;">
                                <strong>Incontournable :</strong> {activite['name'] if activite else 'Information non disponible'} / 
                                <strong>Prix :</strong> {activite['fee'] if activite else 'N/A'}
                            </p>
                        </div>
                    </div>
                    '''

                    popup = Popup(popup_html, max_width=400)
                    folium.Marker(
                        [location_dest.latitude, location_dest.longitude],
                        popup=popup,
                        icon=folium.Icon(color='red')).add_to(carte)
                    folium.PolyLine(
                        [[location.latitude, location.longitude],
                         [location_dest.latitude, location_dest.longitude]],
                        tooltip="Trail").add_to(carte)
                else:
                    print(f"Adresse introuvable : {destination}")
            carte.save("carte_adresse.html")
            carte_html = carte._repr_html_()
            print("Carte créée : carte_adresse.html")
    return render_template('index.html', carte=carte_html, message=message)


def compter_shops(latitude=43.5804,
                  longitude=7.1256,
                  radius=2000,
                  truc="shop"):
    query = f'''
    [out:json][timeout:25];
    (
      node(around:{radius},{latitude},{longitude})[{truc}];
      way(around:{radius},{latitude},{longitude})[{truc}];
      relation(around:{radius},{latitude},{longitude})[{truc}];
    );
    out count;
    '''
    url = 'http://overpass-api.de/api/interpreter'
    try:
        response = requests.post(url, data={'data': query}, timeout=50)
        response.raise_for_status()
        data = response.json()
        count = int(data['elements'][0]['tags']['total'])
        return count
    except Exception as e:
        print(f"Erreur lors de la requête Overpass API : {e}")
        return 0


def get_top_attraction(lat, lon, radius=2000):
    query = f'''
    [out:json][timeout:65];
    (
      node(around:{radius},{lat},{lon})[tourism=attraction];
      way(around:{radius},{lat},{lon})[tourism=attraction];
      relation(around:{radius},{lat},{lon})[tourism=attraction];
    );
    out tags;
    '''
    url = 'http://overpass-api.de/api/interpreter'
    try:
        response = requests.post(url, data={'data': query})
        response.raise_for_status()
        data = response.json()
        elements = data.get('elements', [])

        if not elements:
            print("Aucune attraction trouvée.")
            return None

        # Trier par nombre de tags descendante
        elements.sort(key=lambda el: len(el.get('tags', {})), reverse=True)
        top = elements[0]
        tags = top.get('tags', {})

        attraction_info = {
            'name': tags.get('name', 'Sans nom') or "NA",
            'num_tags': len(tags),
            'fee': tags.get('fee') or tags.get('entrance')
            or "Prix non renseigné",
        }
        return attraction_info

    except Exception as e:
        print(f"Erreur API Overpass : {e}")
        attraction_info = {
            'name': "NA",
            'num_tags': "NA",
            'fee': "NA",
        }
        return attraction_info


df = pd.read_csv('https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/tgvmax/exports/csv?lang=fr&timezone=Europe%2FBerlin&use_labels=true&delimiter=%3B', sep=';')
df = df[~df['ENTITY'].str.contains('AUTOCAR SNCF', na=False)]
df = df[~df['Axe'].str.contains('INTERNATIONAL', na=False)]
df = df.replace(to_replace="PARIS (intramuros)", value="PARIS", regex=False)
df = df.replace(to_replace="LYON (intramuros)", value="LYON", regex=False)
df = df.replace(to_replace="LILLE (intramuros)", value="LILLE", regex=False)
gares_origine = sorted(df['Origine'].unique())


@test.route('/autocomplete')
def autocomplete():
    query = request.args.get('q', '').lower()
    suggestions = [
        gare for gare in gares_origine if gare.lower().startswith(query)
    ]
    return jsonify(suggestions[:10])


if __name__ == '__main__':
    test.run(host='0.0.0.0', port=3000)
