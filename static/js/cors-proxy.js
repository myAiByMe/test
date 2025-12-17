/**
 * cors-proxy.js - Solution pour contourner les restrictions CORS sur GitHub Pages
 * 
 * Ce script permet de faire des requêtes à l'API Anime-Sama depuis GitHub Pages
 * en utilisant un proxy CORS public ou configuré spécifiquement pour le site.
 */

// Liste de serveurs proxy CORS publics que nous pouvons utiliser
const CORS_PROXIES = [
  'https://cors-anywhere.herokuapp.com/',  // Demande une autorisation temporaire
  'https://api.allorigins.win/raw?url=',   // Plus fiable, ne nécessite pas d'autorisation
  'https://corsproxy.io/?',                // Alternative récente
];

// Classe pour gérer les requêtes à travers un proxy CORS
class CorsProxy {
  constructor() {
    this.currentProxyIndex = 1; // Commencer avec allorigins qui est plus fiable
    this.lastProxySuccess = null;
  }

  /**
   * Obtient l'URL du proxy actuellement sélectionné
   */
  getCurrentProxy() {
    return CORS_PROXIES[this.currentProxyIndex];
  }

  /**
   * Change de proxy en cas d'échec
   */
  rotateProxy() {
    this.currentProxyIndex = (this.currentProxyIndex + 1) % CORS_PROXIES.length;
    console.log(`Rotation du proxy CORS vers: ${this.getCurrentProxy()}`);
    return this.getCurrentProxy();
  }

  /**
   * Effectue une requête à travers le proxy CORS
   * @param {string} url - L'URL d'origine à appeler
   * @param {Object} options - Options de la requête fetch
   * @returns {Promise} - La réponse au format JSON
   */
  async fetchWithProxy(url, options = {}) {
    // Vérifier que l'URL est bien pour anime-sama.eu
    if (!url.includes('anime-sama.eu')) {
      throw new Error('Seules les URLs de anime-sama.eu sont autorisées par ce proxy');
    }

    // Si nous avons déjà un proxy qui fonctionne, l'utiliser directement
    if (this.lastProxySuccess) {
      try {
        const proxyUrl = `${this.lastProxySuccess}${encodeURIComponent(url)}`;
        const response = await fetch(proxyUrl, options);
        
        if (!response.ok) {
          throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        return await response.json();
      } catch (error) {
        console.warn(`Le proxy précédemment réussi a échoué: ${error.message}`);
        this.lastProxySuccess = null;
        // Continuez avec le processus de rotation ci-dessous
      }
    }

    // Essayer tous les proxys jusqu'à en trouver un qui fonctionne
    let lastError = null;
    
    // Faire un nombre d'essais égal au nombre de proxys
    for (let i = 0; i < CORS_PROXIES.length; i++) {
      const currentProxy = this.getCurrentProxy();
      const proxyUrl = `${currentProxy}${encodeURIComponent(url)}`;
      
      try {
        console.log(`Tentative avec le proxy: ${currentProxy}`);
        const response = await fetch(proxyUrl, options);
        
        if (!response.ok) {
          throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Enregistrer ce proxy comme fonctionnel
        this.lastProxySuccess = currentProxy;
        console.log(`Proxy réussi: ${currentProxy}`);
        
        return data;
      } catch (error) {
        console.warn(`Échec du proxy ${currentProxy}: ${error.message}`);
        lastError = error;
        this.rotateProxy(); // Essayer le prochain proxy
      }
    }
    
    // Si nous arrivons ici, tous les proxys ont échoué
    throw new Error(`Tous les proxys CORS ont échoué. Dernière erreur: ${lastError?.message}`);
  }

  /**
   * Teste la connectivité de tous les proxys
   * @returns {Promise<string>} - Le premier proxy fonctionnel
   */
  async testProxies() {
    const testUrl = 'https://anime-sama.eu/';
    
    for (let i = 0; i < CORS_PROXIES.length; i++) {
      const proxy = CORS_PROXIES[i];
      const proxyUrl = `${proxy}${encodeURIComponent(testUrl)}`;
      
      try {
        console.log(`Test du proxy: ${proxy}`);
        const response = await fetch(proxyUrl);
        
        if (response.ok) {
          console.log(`Proxy fonctionnel trouvé: ${proxy}`);
          this.currentProxyIndex = i;
          this.lastProxySuccess = proxy;
          return proxy;
        }
      } catch (error) {
        console.warn(`Échec du test pour le proxy ${proxy}: ${error.message}`);
      }
    }
    
    console.error('Aucun proxy fonctionnel trouvé');
    return null;
  }
}

// Instance singleton du proxy CORS
const corsProxy = new CorsProxy();

// Objet global pour interagir avec l'API Anime-Sama
window.AnimeSamaAPI = {
  /**
   * Initialise le proxy CORS
   */
  async init() {
    try {
      await corsProxy.testProxies();
      console.log('Proxy CORS initialisé avec succès');
      return true;
    } catch (error) {
      console.error('Échec de l\'initialisation du proxy CORS:', error);
      return false;
    }
  },
  
  /**
   * Recherche des animes via l'API
   * @param {string} query - Terme de recherche
   * @returns {Promise<Array>} - Liste des animes trouvés
   */
  async searchAnimes(query) {
    try {
      const url = `https://anime-sama.eu/catalogue.json`;
      const data = await corsProxy.fetchWithProxy(url);
      
      // Filtrer les résultats selon la requête
      const results = data.filter(anime => 
        anime.name.toLowerCase().includes(query.toLowerCase())
      );
      
      return results;
    } catch (error) {
      console.error('Erreur lors de la recherche:', error);
      throw error;
    }
  },
  
  /**
   * Récupère les saisons d'un anime
   * @param {string} animeUrl - URL de l'anime
   * @returns {Promise<Array>} - Saisons de l'anime
   */
  async getAnimeSeasons(animeUrl) {
    try {
      // Format d'URL attendu: https://anime-sama.eu/anime/naruto/
      const url = animeUrl;
      const htmlContent = await corsProxy.fetchWithProxy(url, {
        headers: { 'Accept': 'text/html' }
      });
      
      // Extraction des saisons à partir du HTML
      // Note: Cette fonction est simplifiée et nécessiterait une analyse HTML
      // Pour l'instant, nous renvoyons simplement les données brutes
      return htmlContent;
    } catch (error) {
      console.error('Erreur lors de la récupération des saisons:', error);
      throw error;
    }
  },
  
  /**
   * Récupère les épisodes d'une saison
   * @param {string} seasonUrl - URL de la saison
   * @returns {Promise<Array>} - Épisodes de la saison
   */
  async getSeasonEpisodes(seasonUrl) {
    try {
      const url = seasonUrl;
      const htmlContent = await corsProxy.fetchWithProxy(url, {
        headers: { 'Accept': 'text/html' }
      });
      
      // Extraction des épisodes à partir du HTML
      // Note: Cette fonction est simplifiée et nécessiterait une analyse HTML
      return htmlContent;
    } catch (error) {
      console.error('Erreur lors de la récupération des épisodes:', error);
      throw error;
    }
  }
};

// Initialisation automatique lors du chargement
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const initialized = await window.AnimeSamaAPI.init();
    if (initialized) {
      console.log('API Anime-Sama prête à être utilisée');
      
      // Déclencher un événement pour notifier que l'API est prête
      const event = new CustomEvent('animesama-api-ready');
      document.dispatchEvent(event);
    } else {
      console.error('Impossible d\'initialiser l\'API Anime-Sama');
    }
  } catch (error) {
    console.error('Erreur lors de l\'initialisation de l\'API:', error);
  }
});