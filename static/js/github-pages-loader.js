/**
 * github-pages-loader.js - Chargeur de données pour la version GitHub Pages
 * 
 * Ce script gère le chargement des données d'anime lorsque le site est
 * hébergé sur GitHub Pages, en contournant les restrictions CORS grâce
 * au script cors-proxy.js.
 */

// Définition de l'objet global GithubPagesLoader
window.GithubPagesLoader = {
    // URL statique pour les données pré-enregistrées
    DATA_URL: 'https://anime-sama.eu/catalogue.json',
    
    // Cache local pour éviter trop de requêtes
    cache: {
        popularAnimes: null,
        recentAnimes: null,
        genres: null
    },
    
    /**
     * Initialise le chargeur de données
     */
    init() {
        console.log('Initialisation du chargeur GitHub Pages');
        
        // Vérifie si l'API CORS est disponible
        if (!window.AnimeSamaAPI) {
            console.error('AnimeSamaAPI non disponible. Assurez-vous que cors-proxy.js est chargé avant ce script.');
            this.showError('Erreur de chargement de l\'API');
            return;
        }
        
        // Chargement initial des données
        this.loadPopularAnimes();
        this.loadRecentAnimes();
        
        // Gestion de la recherche pour GitHub Pages
        const searchForm = document.getElementById('searchForm');
        if (searchForm) {
            searchForm.addEventListener('submit', event => {
                if (window.location.hostname.includes('github.io')) {
                    event.preventDefault();
                    const query = document.getElementById('searchInput').value.trim();
                    if (query) {
                        // Stocker la requête dans sessionStorage
                        sessionStorage.setItem('animeSearch', query);
                        window.location.href = 'search.html';
                    }
                }
            });
        }
        
        // Vérifier si nous sommes sur la page de recherche
        if (window.location.pathname.includes('search.html')) {
            this.handleSearchPage();
        }
        
        // Vérifier si nous sommes sur la page de détail d'un anime
        if (window.location.pathname.includes('anime/')) {
            this.handleAnimePage();
        }
    },
    
    /**
     * Charge les animes populaires
     */
    async loadPopularAnimes() {
        // Éléments pré-définis si tout échoue
        const fallbackPopularAnimes = [
            { id: 1, title: 'Naruto', image: 'img/anime-placeholder.jpg' },
            { id: 2, title: 'One Piece', image: 'img/anime-placeholder.jpg' },
            { id: 3, title: 'Dragon Ball', image: 'img/anime-placeholder.jpg' },
            { id: 4, title: 'Bleach', image: 'img/anime-placeholder.jpg' },
            { id: 5, title: 'Death Note', image: 'img/anime-placeholder.jpg' },
            { id: 6, title: 'Attack on Titan', image: 'img/anime-placeholder.jpg' }
        ];
        
        const popularAnimesContainer = document.getElementById('popularAnimes');
        if (!popularAnimesContainer) return;
        
        try {
            // Si nous avons déjà les données en cache, les utiliser
            if (this.cache.popularAnimes) {
                this.renderAnimeGrid(popularAnimesContainer, this.cache.popularAnimes);
                return;
            }
            
            // Tenter de récupérer les données via le proxy CORS
            console.log('Chargement des animes populaires via le proxy CORS');
            
            // Attendre que l'API soit prête
            await new Promise(resolve => {
                if (document.animeSamaApiReady) {
                    resolve();
                } else {
                    document.addEventListener('animesama-api-ready', () => resolve());
                }
            });
            
            // Récupérer le catalogue complet
            const data = await window.AnimeSamaAPI.searchAnimes('');
            
            if (Array.isArray(data) && data.length > 0) {
                // Prendre les 12 premiers animes (ou tous si moins)
                const popularAnimes = data.slice(0, 12).map(anime => ({
                    id: anime.id || Math.floor(Math.random() * 10000),
                    title: anime.name,
                    image: anime.image_url || 'img/anime-placeholder.jpg'
                }));
                
                // Mettre en cache
                this.cache.popularAnimes = popularAnimes;
                
                // Afficher
                this.renderAnimeGrid(popularAnimesContainer, popularAnimes);
            } else {
                throw new Error('Format de données inattendu');
            }
        } catch (error) {
            console.error('Erreur lors du chargement des animes populaires:', error);
            // Utiliser les données de secours
            this.renderAnimeGrid(popularAnimesContainer, fallbackPopularAnimes);
        }
    },
    
    /**
     * Charge les animes récents
     */
    async loadRecentAnimes() {
        // Élément de chargement
        const recentAnimesContainer = document.getElementById('recentAnimes');
        if (!recentAnimesContainer) return;
        
        try {
            // Si nous avons déjà les données en cache, les utiliser
            if (this.cache.recentAnimes) {
                this.renderAnimeGrid(recentAnimesContainer, this.cache.recentAnimes);
                return;
            }
            
            // Tenter de récupérer les données via le proxy CORS
            console.log('Chargement des animes récents via le proxy CORS');
            
            // Attendre que l'API soit prête
            await new Promise(resolve => {
                if (document.animeSamaApiReady) {
                    resolve();
                } else {
                    document.addEventListener('animesama-api-ready', () => resolve());
                }
            });
            
            // Pour le moment, nous utilisons les mêmes données que popularAnimes
            // mais dans un ordre différent
            let recentAnimes = [];
            
            if (this.cache.popularAnimes) {
                // Créer une copie et mélanger
                recentAnimes = [...this.cache.popularAnimes];
                recentAnimes.sort(() => Math.random() - 0.5);
            } else {
                // Récupérer le catalogue complet
                const data = await window.AnimeSamaAPI.searchAnimes('');
                
                if (Array.isArray(data) && data.length > 0) {
                    // Prendre les 12 animes au hasard
                    const shuffled = [...data].sort(() => Math.random() - 0.5);
                    recentAnimes = shuffled.slice(0, 12).map(anime => ({
                        id: anime.id || Math.floor(Math.random() * 10000),
                        title: anime.name,
                        image: anime.image_url || 'img/anime-placeholder.jpg'
                    }));
                } else {
                    throw new Error('Format de données inattendu');
                }
            }
            
            // Mettre en cache
            this.cache.recentAnimes = recentAnimes;
            
            // Afficher
            this.renderAnimeGrid(recentAnimesContainer, recentAnimes);
        } catch (error) {
            console.error('Erreur lors du chargement des animes récents:', error);
            // Afficher un message d'erreur
            recentAnimesContainer.innerHTML = `
                <div class="error-message">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>Impossible de charger les animes récents.</p>
                </div>
            `;
        }
    },
    
    /**
     * Gère le comportement de la page de recherche
     */
    handleSearchPage() {
        // Récupérer la requête
        const urlParams = new URLSearchParams(window.location.search);
        const query = urlParams.get('query') || sessionStorage.getItem('animeSearch') || '';
        const genre = urlParams.get('genre') || '';
        
        // Titre de recherche
        const searchTitle = document.querySelector('.search-title') || document.querySelector('h1');
        if (searchTitle) {
            if (query) {
                searchTitle.textContent = `Résultats pour: "${query}"`;
            } else if (genre) {
                searchTitle.textContent = `Animes du genre: ${genre}`;
            }
        }
        
        // Conteneur des résultats
        const resultsContainer = document.querySelector('.search-results') || document.querySelector('.animes-grid');
        if (!resultsContainer) return;
        
        // Afficher chargement
        resultsContainer.innerHTML = `
            <div class="loading-spinner">
                <i class="fas fa-spinner fa-spin"></i>
                <p>Recherche en cours...</p>
            </div>
        `;
        
        // Effectuer la recherche
        this.searchAnimes(query, genre)
            .then(results => {
                if (results.length > 0) {
                    this.renderAnimeGrid(resultsContainer, results);
                } else {
                    resultsContainer.innerHTML = `
                        <div class="no-results">
                            <i class="fas fa-search"></i>
                            <p>Aucun résultat trouvé pour "${query || genre}".</p>
                        </div>
                    `;
                }
            })
            .catch(error => {
                console.error('Erreur de recherche:', error);
                resultsContainer.innerHTML = `
                    <div class="error-message">
                        <i class="fas fa-exclamation-circle"></i>
                        <p>Une erreur est survenue lors de la recherche.</p>
                    </div>
                `;
            });
    },
    
    /**
     * Gère le comportement de la page de détail d'anime
     */
    handleAnimePage() {
        // Extraire l'ID de l'anime de l'URL
        const pathMatch = window.location.pathname.match(/\/anime\/(\d+)/);
        if (!pathMatch) return;
        
        const animeId = pathMatch[1];
        console.log(`Chargement des détails pour l'anime ID: ${animeId}`);
        
        // TODO: Implémenter le chargement des détails de l'anime
        // Pour l'instant, nous affichons uniquement un message
        const animeContainer = document.querySelector('.anime-detail');
        if (animeContainer) {
            animeContainer.innerHTML = `
                <div class="github-pages-notice">
                    <p><i class="fas fa-info-circle"></i> Les détails complets des animes ne sont pas disponibles dans la version GitHub Pages. Veuillez utiliser la version complète du site.</p>
                </div>
            `;
        }
    },
    
    /**
     * Cherche des animes par nom ou genre
     * @param {string} query - Terme de recherche
     * @param {string} genre - Genre pour filtrer
     * @returns {Promise<Array>} - Résultats de recherche
     */
    async searchAnimes(query, genre) {
        try {
            // Attendre que l'API soit prête
            await new Promise(resolve => {
                if (document.animeSamaApiReady) {
                    resolve();
                } else {
                    document.addEventListener('animesama-api-ready', () => resolve());
                }
            });
            
            // Récupérer le catalogue
            const data = await window.AnimeSamaAPI.searchAnimes(query || '');
            
            if (!Array.isArray(data)) {
                throw new Error('Format de données inattendu');
            }
            
            // Filtrer par genre si spécifié
            let results = data;
            if (genre) {
                results = results.filter(anime => 
                    anime.genres && 
                    anime.genres.some(g => g.toLowerCase() === genre.toLowerCase())
                );
            }
            
            // Formater les résultats
            return results.map(anime => ({
                id: anime.id || Math.floor(Math.random() * 10000),
                title: anime.name,
                image: anime.image_url || 'img/anime-placeholder.jpg'
            }));
        } catch (error) {
            console.error('Erreur de recherche:', error);
            throw error;
        }
    },
    
    /**
     * Affiche une grille d'animes dans un conteneur
     * @param {HTMLElement} container - Élément conteneur
     * @param {Array} animes - Liste d'animes à afficher
     */
    renderAnimeGrid(container, animes) {
        if (!container || !Array.isArray(animes)) return;
        
        // Vider le conteneur
        container.innerHTML = '';
        
        // Créer un élément pour chaque anime
        animes.forEach(anime => {
            const animeCard = document.createElement('div');
            animeCard.className = 'anime-card';
            animeCard.innerHTML = `
                <a href="#" class="anime-link" data-id="${anime.id}">
                    <div class="anime-poster">
                        <img src="${anime.image}" alt="${anime.title}" onerror="this.src='img/anime-placeholder.jpg'">
                    </div>
                    <div class="anime-info">
                        <h3 class="anime-title">${anime.title}</h3>
                    </div>
                </a>
            `;
            
            // Ajouter au conteneur
            container.appendChild(animeCard);
            
            // Ajouter un gestionnaire d'événements pour les clics
            const animeLink = animeCard.querySelector('.anime-link');
            if (animeLink) {
                animeLink.addEventListener('click', (event) => {
                    event.preventDefault();
                    this.showGitHubPagesNotice();
                });
            }
        });
    },
    
    /**
     * Affiche une notice indiquant que certaines fonctionnalités 
     * ne sont pas disponibles dans la version GitHub Pages
     */
    showGitHubPagesNotice() {
        // Créer la modal si elle n'existe pas
        let modal = document.getElementById('github-pages-modal');
        
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'github-pages-modal';
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <span class="close">&times;</span>
                    <h2>Fonctionnalité limitée</h2>
                    <p>Vous consultez la version statique de AnimeZone hébergée sur GitHub Pages.</p>
                    <p>Cette fonctionnalité n'est disponible que dans la version complète du site.</p>
                </div>
            `;
            document.body.appendChild(modal);
            
            // Fermeture de la modal
            const closeBtn = modal.querySelector('.close');
            closeBtn.addEventListener('click', () => {
                modal.style.display = 'none';
            });
            
            // Fermer la modal en cliquant à l'extérieur
            window.addEventListener('click', (event) => {
                if (event.target === modal) {
                    modal.style.display = 'none';
                }
            });
        }
        
        // Afficher la modal
        modal.style.display = 'block';
    },
    
    /**
     * Affiche un message d'erreur
     * @param {string} message - Message d'erreur
     */
    showError(message) {
        // Ajouter une bannière d'erreur en haut de la page
        const errorBanner = document.createElement('div');
        errorBanner.className = 'error-banner';
        errorBanner.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <p>${message}</p>
            <button class="close-btn">&times;</button>
        `;
        
        // Insérer au début du body
        document.body.insertBefore(errorBanner, document.body.firstChild);
        
        // Fermeture de la bannière
        const closeBtn = errorBanner.querySelector('.close-btn');
        closeBtn.addEventListener('click', () => {
            errorBanner.remove();
        });
    }
};