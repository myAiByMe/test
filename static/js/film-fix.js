/**
 * film-fix.js - Script qui assure le bon affichage des films dans AnimeZone
 */

document.addEventListener('DOMContentLoaded', function() {
    // Fonction pour s'assurer que l'onglet des films est correctement affiché
    function fixFilmsTab() {
        console.log("Correction de l'affichage des films...");
        
        // Vérifier si nous sommes sur une page d'anime
        const seasonsContainer = document.querySelector('.seasons-tabs');
        if (!seasonsContainer) return;
        
        // Vérifier si nous avons un onglet pour les films (saison 99)
        const filmsTab = document.querySelector('.season-tab[data-season="99"]');
        if (!filmsTab) {
            console.log("Aucun onglet de films trouvé");
            return;
        }
        
        console.log("Onglet de films trouvé, application des correctifs");
        
        // S'assurer que le texte est bien "Films"
        if (filmsTab.textContent.trim() !== 'Films') {
            filmsTab.textContent = 'Films';
        }
        
        // Ajouter une classe spéciale
        filmsTab.classList.add('films-tab');
        
        // Récupérer le contenu des films
        const filmsContent = document.querySelector('.season-content[data-season="99"]');
        if (filmsContent) {
            // Ajouter une classe spéciale
            filmsContent.classList.add('films-content');
            
            // Modifier les icônes des films
            const playIcons = filmsContent.querySelectorAll('.fa-play-circle');
            playIcons.forEach(icon => {
                icon.classList.remove('fa-play-circle');
                icon.classList.add('fa-film');
            });
            
            // Ajouter un titre spécial avant la liste des épisodes
            const episodesList = filmsContent.querySelector('.episodes-list');
            if (episodesList && !filmsContent.querySelector('.films-header')) {
                const filmsHeader = document.createElement('div');
                filmsHeader.className = 'films-header';
                filmsHeader.innerHTML = '<h3>Films disponibles</h3>';
                filmsContent.insertBefore(filmsHeader, episodesList);
            }
        }
        
        console.log("Correctifs pour l'affichage des films appliqués");
    }
    
    // Exécuter la correction après un court délai
    setTimeout(fixFilmsTab, 500);
    
    // Aussi lors des clics sur les onglets
    document.addEventListener('click', function(event) {
        if (event.target.classList.contains('season-tab')) {
            setTimeout(fixFilmsTab, 100);
        }
    });
});