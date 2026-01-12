// Application state
const state = {
    currentSport: 'football',
    currentDate: new Date(),
    autoRefresh: true,
    refreshInterval: null,
};

// API configuration - derive base path from current URL
// Removes '/dashboard' from path to get the API root
const basePath = window.location.pathname.replace(/\/dashboard$/, '');
const API_BASE = window.location.origin + basePath;

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    updateDateDisplay();
    loadMatches();
    setupAutoRefresh();
});

// Event listeners
function initializeEventListeners() {
    // Sport tabs
    document.querySelectorAll('.sport-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            const sport = e.target.dataset.sport;
            switchSport(sport);
        });
    });

    // Date navigation
    document.getElementById('prevDay').addEventListener('click', () => {
        changeDate(-1);
    });

    document.getElementById('nextDay').addEventListener('click', () => {
        changeDate(1);
    });

    // Auto-refresh toggle
    document.getElementById('autoRefresh').addEventListener('change', (e) => {
        state.autoRefresh = e.target.checked;
        setupAutoRefresh();
    });
}

// Switch sport tab
function switchSport(sport) {
    state.currentSport = sport;

    // Update active tab
    document.querySelectorAll('.sport-tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.dataset.sport === sport) {
            tab.classList.add('active');
        }
    });

    loadMatches();
}

// Change date
function changeDate(days) {
    state.currentDate.setDate(state.currentDate.getDate() + days);
    updateDateDisplay();
    loadMatches();
}

// Update date display
function updateDateDisplay() {
    const options = {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    };
    const dateString = state.currentDate.toLocaleDateString('en-US', options);
    document.getElementById('currentDate').textContent = dateString;
}

// Format date for API
function formatDateForAPI(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// Load matches from API
async function loadMatches() {
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const matchesContainer = document.getElementById('matchesContainer');
    const emptyState = document.getElementById('emptyState');

    // Show loading
    loading.style.display = 'block';
    error.style.display = 'none';
    emptyState.style.display = 'none';
    matchesContainer.innerHTML = '';

    try {
        const dateStr = formatDateForAPI(state.currentDate);
        const url = `${API_BASE}/matches/by-date/grouped?date=${dateStr}&sport=${state.currentSport}`;

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Hide loading
        loading.style.display = 'none';

        // Check if we have matches
        if (Object.keys(data).length === 0) {
            emptyState.style.display = 'block';
            return;
        }

        // Render matches grouped by league
        renderMatches(data);

    } catch (err) {
        loading.style.display = 'none';
        error.style.display = 'block';
        error.textContent = `Error loading matches: ${err.message}`;
        console.error('Error loading matches:', err);
    }
}

// Render matches grouped by league
function renderMatches(groupedMatches) {
    const container = document.getElementById('matchesContainer');
    container.innerHTML = '';

    // Sort leagues alphabetically
    const leagues = Object.keys(groupedMatches).sort();

    leagues.forEach(leagueName => {
        const matches = groupedMatches[leagueName];

        // Create league section
        const leagueSection = document.createElement('div');
        leagueSection.className = 'league-section';

        // League header
        const leagueHeader = document.createElement('h2');
        leagueHeader.className = 'league-name';
        leagueHeader.textContent = leagueName;
        leagueSection.appendChild(leagueHeader);

        // Matches list
        const matchesList = document.createElement('div');
        matchesList.className = 'matches-list';

        matches.forEach(match => {
            const matchCard = createMatchCard(match);
            matchesList.appendChild(matchCard);
        });

        leagueSection.appendChild(matchesList);
        container.appendChild(leagueSection);
    });
}

// Create a match card
function createMatchCard(match) {
    const card = document.createElement('div');
    card.className = `match-card status-${match.status}`;

    // Live indicator
    const liveIndicator = match.status === 'inprogress'
        ? '<span class="live-indicator"></span>'
        : '';

    // Format time
    const matchTime = new Date(match.start_time);
    const timeStr = matchTime.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
    });

    // Format score
    let scoreDisplay;
    if (match.status === 'notstarted') {
        scoreDisplay = '<span class="score-vs">vs</span>';
    } else {
        scoreDisplay = `
            <span class="score">${match.home_score} - ${match.away_score}</span>
        `;
    }

    // Status display
    let statusDisplay = '';
    switch (match.status) {
        case 'inprogress':
            statusDisplay = 'Live';
            break;
        case 'finished':
            statusDisplay = 'FT';
            break;
        case 'notstarted':
            statusDisplay = timeStr;
            break;
        case 'postponed':
            statusDisplay = 'Postponed';
            break;
        case 'cancelled':
            statusDisplay = 'Cancelled';
            break;
        default:
            statusDisplay = match.status;
    }

    card.innerHTML = `
        <div class="match-teams">
            <div class="team home-team">
                <span class="team-name">${match.home_team.name}</span>
            </div>
            <div class="match-score">
                ${scoreDisplay}
            </div>
            <div class="team away-team">
                <span class="team-name">${match.away_team.name}</span>
            </div>
        </div>
        <div class="match-info">
            ${liveIndicator}
            <span class="match-time">${statusDisplay}</span>
        </div>
    `;

    return card;
}

// Setup auto-refresh
function setupAutoRefresh() {
    // Clear existing interval
    if (state.refreshInterval) {
        clearInterval(state.refreshInterval);
        state.refreshInterval = null;
    }

    // Setup new interval if enabled
    if (state.autoRefresh) {
        state.refreshInterval = setInterval(() => {
            loadMatches();
        }, 30000); // 30 seconds
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (state.refreshInterval) {
        clearInterval(state.refreshInterval);
    }
});
