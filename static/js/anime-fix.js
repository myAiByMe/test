/**
 * anime-fix.js - Script pour améliorer l'expérience d'affichage des animes
 * Inclut des corrections spécifiques pour les films (saison 99)
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log("AnimeZone: Initialisation des corrections d'affichage");
    
    // Amélioration pour les films
    fixFilmsDisplay();
    
    // Défilement des saisons amélioré
    initSeasonScrolling();
    
    // Correction des icônes pour les différents types de contenus
    updateContentIcons();
});

/**
 * Corrige l'affichage des films (saison 99)
 */
function fixFilmsDisplay() {
    // Identifier l'onglet des films (saison 99)
    const filmsTab = document.querySelector('.season-tab[data-season="99"]');
    if (!filmsTab) {
        console.log("Aucun film trouvé pour cet anime");
        return;
    }
    
    console.log("Films détectés - application des correctifs d'affichage");
    
    // S'assurer que le texte est bien 'Films'
    if (filmsTab.textContent.trim() !== 'Films') {
        filmsTab.textContent = 'Films';
    }
    
    // Ajouter une classe spéciale pour le style
    filmsTab.classList.add('films-tab');
    
    // Améliorer le contenu des films
    const filmsContent = document.querySelector('.season-content[data-season="99"]');
    if (filmsContent) {
        // Ajouter une classe pour le style
        filmsContent.classList.add('films-content');
        
        // Ajouter un header explicatif
        if (!filmsContent.querySelector('.films-header')) {
            const header = document.createElement('div');
            header.className = 'films-header';
            header.innerHTML = '<h3>Films disponibles</h3>';
            
            // Insérer avant la liste des épisodes
            const episodesList = filmsContent.querySelector('.episodes-list');
            if (episodesList) {
                filmsContent.insertBefore(header, episodesList);
            }
        }
        
        // Modifier les icônes pour les films
        const playIcons = filmsContent.querySelectorAll('.fa-play-circle');
        playIcons.forEach(icon => {
            icon.classList.remove('fa-play-circle');
            icon.classList.add('fa-film');
        });
    }
}

/**
 * Initialise le défilement amélioré des saisons
 */
function initSeasonScrolling() {
    // Vérifier si nous sommes sur une page avec des saisons
    const seasonsContainer = document.getElementById('seasonsTabsContainer');
    if (!seasonsContainer) return;
    
    // S'assurer que le conteneur a la bonne classe
    if (seasonsContainer.parentElement && !seasonsContainer.parentElement.classList.contains('anime-seasons-tabs')) {
        seasonsContainer.parentElement.classList.add('anime-seasons-tabs');
        seasonsContainer.classList.add('anime-seasons-container');
    }
    
    // Fonction globale pour le défilement (si on a besoin de navigation horizontale)
    window.scrollSeasons = function(direction) {
        const scrollAmount = 250; // Quantité de défilement en pixels
        
        if (direction === 'left') {
            seasonsContainer.scrollLeft -= scrollAmount;
        } else {
            seasonsContainer.scrollLeft += scrollAmount;
        }
    };
    
    // Dans le nouveau design, nous n'avons plus besoin des boutons de défilement
    // car les saisons sont affichées en multi-lignes
}

/**
 * Met à jour les icônes en fonction du type de contenu
 */
function updateContentIcons() {
    // Pour les films, on a déjà fait la modification dans fixFilmsDisplay()
    
    // Pour les saisons "Kai", on pourrait ajouter des icônes spéciales
    const kaiSeasonTabs = Array.from(document.querySelectorAll('.season-tab')).filter(tab => 
        tab.textContent.trim().toLowerCase().includes('kai')
    );
    
    kaiSeasonTabs.forEach(tab => {
        tab.classList.add('kai-tab');
        const seasonNumber = tab.getAttribute('data-season');
        const content = document.querySelector(`.season-content[data-season="${seasonNumber}"]`);
        
        if (content) {
            content.classList.add('kai-content');
            // On pourrait également modifier les icônes pour ces épisodes spéciaux
        }
    });
}