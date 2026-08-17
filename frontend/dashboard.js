/**
 * NutriTrack — Dashboard & Food Entry Module
 * Handles progress ring, food image capture, entry list, and animations.
 */
(function () {
  'use strict';

  // ============================================
  // Constants
  // ============================================
  var COLOR_GREEN = '#00d68f';
  var COLOR_ORANGE = '#ff9f43';
  var COLOR_RED = '#ff6b6b';
  var COLOR_REMAINING = '#2a2a4a';

  // ============================================
  // State
  // ============================================
  var progressChart = null;
  var currentCalories = 0;
  var currentGoal = 0;
  var confettiTriggered = false;

  // ============================================
  // Helpers
  // ============================================

  /**
   * Get today's date in YYYY-MM-DD format.
   */
  function getTodayISO() {
    var d = new Date();
    var year = d.getFullYear();
    var month = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    return year + '-' + month + '-' + day;
  }

  /**
   * Format a date string for display (e.g., "Jan 15, 2024").
   */
  function formatDateDisplay(isoDate) {
    var parts = isoDate.split('-');
    var d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    return d.toLocaleDateString('es-ES', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  /**
   * Determine the ring color based on calorie ratio.
   */
  function getRingColor(consumed, goal) {
    if (goal <= 0) return COLOR_GREEN;
    var ratio = consumed / goal;
    if (ratio > 1) return COLOR_RED;
    if (ratio > 0.8) return COLOR_ORANGE;
    return COLOR_GREEN;
  }

  // ============================================
  // Progress Ring (Chart.js Doughnut)
  // ============================================

  /**
   * Initialize or update the Chart.js doughnut chart.
   */
  function renderProgressRing(consumed, goal) {
    var canvas = document.getElementById('progress-ring-chart');
    if (!canvas) return;

    var remaining = Math.max(0, goal - consumed);
    var color = getRingColor(consumed, goal);

    var data = {
      datasets: [{
        data: [consumed, remaining],
        backgroundColor: [color, COLOR_REMAINING],
        borderWidth: 0,
        cutout: '78%'
      }]
    };

    var options = {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: { enabled: false }
      },
      animation: {
        animateRotate: true,
        duration: 800
      }
    };

    if (progressChart) {
      // Update existing chart
      progressChart.data.datasets[0].data = [consumed, remaining];
      progressChart.data.datasets[0].backgroundColor = [color, COLOR_REMAINING];
      progressChart.update();
    } else {
      // Create new chart
      if (typeof Chart !== 'undefined') {
        progressChart = new Chart(canvas, {
          type: 'doughnut',
          data: data,
          options: options
        });
      }
    }
  }

  /**
   * Animate the calorie counter from previous to new value.
   */
  function animateCounter(fromValue, toValue, duration) {
    var el = document.getElementById('calories-consumed');
    if (!el) return;

    var startTime = null;
    duration = duration || 600;

    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min((timestamp - startTime) / duration, 1);
      // Ease out cubic
      var eased = 1 - Math.pow(1 - progress, 3);
      var current = Math.round(fromValue + (toValue - fromValue) * eased);
      el.textContent = current;

      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = toValue;
      }
    }

    requestAnimationFrame(step);
  }

  /**
   * Update the goal label text.
   */
  function updateGoalLabel(goal) {
    var el = document.getElementById('calories-goal-label');
    if (el) {
      el.textContent = '/ ' + goal + ' kcal';
    }
  }

  // ============================================
  // Entry List Rendering
  // ============================================

  /**
   * Render a list of food entries in the entries container.
   */
  function renderEntries(entries) {
    var list = document.getElementById('entries-list');
    if (!list) return;

    list.innerHTML = '';

    if (!entries || entries.length === 0) {
      var emptyMsg = document.createElement('p');
      emptyMsg.style.color = 'var(--text-secondary)';
      emptyMsg.style.textAlign = 'center';
      emptyMsg.style.padding = 'var(--spacing-lg)';
      emptyMsg.textContent = 'Sin entradas aún. ¡Toca la cámara para agregar comida!';
      list.appendChild(emptyMsg);
      return;
    }

    entries.forEach(function (entry, index) {
      var card = document.createElement('div');
      card.className = 'entry-card';
      card.setAttribute('role', 'listitem');
      card.style.animationDelay = (index * 0.08) + 's';
      card.style.opacity = '0';
      card.style.animation = 'fadeInUp 0.4s ease forwards';
      card.style.animationDelay = (index * 0.08) + 's';

      var info = document.createElement('div');
      info.className = 'entry-info';

      var name = document.createElement('span');
      name.className = 'entry-name';
      name.textContent = entry.food_name || 'Comida desconocida';

      var meta = document.createElement('span');
      meta.className = 'entry-meta';
      var confidence = entry.confidence != null ? Math.round(entry.confidence * 100) + '% confianza' : '';
      var time = entry.timestamp ? formatTime(entry.timestamp) : '';
      meta.textContent = [time, confidence].filter(Boolean).join(' · ');

      info.appendChild(name);
      info.appendChild(meta);

      var cals = document.createElement('span');
      cals.className = 'entry-calories';
      cals.textContent = (entry.calories || 0) + ' kcal';

      var deleteBtn = document.createElement('button');
      deleteBtn.textContent = '✕';
      deleteBtn.style.cssText = 'background:none;border:none;color:var(--accent-danger);font-size:1.2rem;cursor:pointer;padding:4px 8px;';
      deleteBtn.setAttribute('aria-label', 'Eliminar entrada');
      deleteBtn.addEventListener('click', function () {
        deleteEntry(entry.entry_id, entry.date);
      });

      var rightSide = document.createElement('div');
      rightSide.style.cssText = 'display:flex;align-items:center;gap:8px;';
      rightSide.appendChild(cals);
      rightSide.appendChild(deleteBtn);

      card.appendChild(info);
      card.appendChild(rightSide);
      list.appendChild(card);
    });
  }

  /**
   * Format an ISO timestamp to a short time string.
   */
  function formatTime(isoTimestamp) {
    try {
      var d = new Date(isoTimestamp);
      return d.toLocaleTimeString('es-ES', { hour: 'numeric', minute: '2-digit' });
    } catch (e) {
      return '';
    }
  }

  // ============================================
  // Camera / Gallery Image Capture
  // ============================================

  /**
   * Set up camera button and file input handlers.
   */
  function setupImageCapture() {
    var cameraBtn = document.getElementById('camera-btn');
    var fileInput = document.getElementById('food-image-input');

    if (!cameraBtn || !fileInput) return;

    cameraBtn.addEventListener('click', function () {
      fileInput.click();
    });

    fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) return;

      // Validate file size (max 20MB)
      if (file.size > 20 * 1024 * 1024) {
        alert('La imagen es demasiado grande. El tamaño máximo es 20MB.');
        fileInput.value = '';
        return;
      }

      // Convert to base64 and submit
      var reader = new FileReader();
      reader.onload = function (e) {
        var base64 = e.target.result;
        // Remove the data:image/...;base64, prefix
        var base64Data = base64.split(',')[1] || base64;
        submitFoodEntry(base64Data);
      };
      reader.readAsDataURL(file);

      // Reset input so same file can be re-selected
      fileInput.value = '';
    });
  }

  // ============================================
  // API Interactions
  // ============================================

  /**
   * Show or hide the loading spinner.
   */
  function showSpinner(visible) {
    var spinner = document.getElementById('dashboard-spinner');
    if (spinner) {
      if (visible) {
        spinner.classList.add('visible');
      } else {
        spinner.classList.remove('visible');
      }
    }
  }

  /**
   * Delete a food entry and refresh the dashboard.
   */
  async function deleteEntry(entryId, date) {
    if (!confirm('¿Eliminar esta entrada?')) return;

    try {
      await window.NutriTrack.apiRequest('DELETE', '/entries', {
        entry_id: entryId,
        date: date
      });
      await loadDailySummary();
    } catch (err) {
      alert(err.message || 'Error al eliminar entrada.');
    }
  }

  /**
   * Submit a food entry image to the API.
   */
  async function submitFoodEntry(base64Data) {
    showSpinner(true);

    try {
      var response = await window.NutriTrack.apiRequest('POST', '/entries', {
        image_data: base64Data
      });

      // Update dashboard with the response
      if (response && response.daily_summary) {
        updateDashboardFromSummary(response.daily_summary);
      } else if (response && response.entry) {
        // Fallback: refresh the full summary
        await loadDailySummary();
      }
    } catch (err) {
      var message = err.message || 'Error al analizar la imagen. Intenta de nuevo.';
      alert(message);
    } finally {
      showSpinner(false);
    }
  }

  /**
   * Load the daily summary from the API.
   */
  async function loadDailySummary() {
    var today = getTodayISO();

    try {
      var summary = await window.NutriTrack.apiRequest('GET', '/summary?date=' + today);
      if (summary) {
        updateDashboardFromSummary(summary);
      }
    } catch (err) {
      // Silently fail on load — dashboard will show zeros
      console.error('Failed to load daily summary:', err.message);
    }
  }

  /**
   * Update all dashboard elements from a summary object.
   */
  function updateDashboardFromSummary(summary) {
    var totalCalories = summary.total_calories || 0;
    var goal = (summary.goal && summary.goal.target_calories) || 0;
    var entries = summary.entries || [];
    var status = summary.status || 'within_goal';

    var previousCalories = currentCalories;
    currentCalories = totalCalories;
    currentGoal = goal;

    // Update progress ring
    renderProgressRing(totalCalories, goal);
    updateGoalLabel(goal);

    // Animate calorie counter
    animateCounter(previousCalories, totalCalories);

    // Render entries
    renderEntries(entries);

    // Handle animations based on status
    handleGoalAnimations(totalCalories, goal, status);
  }

  // ============================================
  // Celebration & Warning Animations
  // ============================================

  /**
   * Trigger confetti or shake based on goal status.
   */
  function handleGoalAnimations(totalCalories, goal, status) {
    if (status === 'exceeded' || totalCalories > goal) {
      // Shake the calorie display
      triggerShake();
    } else if (totalCalories > 0 && totalCalories <= goal && !confettiTriggered) {
      // Goal is met (within goal and has entries) — celebrate!
      triggerConfetti();
      confettiTriggered = true;
    }
  }

  /**
   * Trigger Canvas Confetti animation.
   */
  function triggerConfetti() {
    if (typeof confetti === 'function') {
      confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.6 }
      });
    }
  }

  /**
   * Trigger shake animation on the calorie display.
   */
  function triggerShake() {
    var el = document.getElementById('calories-consumed');
    if (!el) return;

    el.classList.add('animate-shake');
    el.addEventListener('animationend', function handler() {
      el.classList.remove('animate-shake');
      el.removeEventListener('animationend', handler);
    });
  }

  // ============================================
  // Date Display
  // ============================================

  /**
   * Set the dashboard date label.
   */
  function setDateDisplay() {
    var el = document.getElementById('dashboard-date');
    if (el) {
      el.textContent = formatDateDisplay(getTodayISO());
    }
  }

  // ============================================
  // Dashboard Screen Observer
  // ============================================

  /**
   * Detect when dashboard becomes visible and refresh data.
   */
  function setupScreenObserver() {
    var dashboardScreen = document.getElementById('dashboard-screen');
    if (!dashboardScreen) return;

    // Use MutationObserver to detect when the screen becomes active
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
          if (dashboardScreen.classList.contains('active')) {
            onDashboardVisible();
          }
        }
      });
    });

    observer.observe(dashboardScreen, { attributes: true });
  }

  /**
   * Called when the dashboard screen becomes visible.
   */
  function onDashboardVisible() {
    // Reset confetti flag for new view
    confettiTriggered = false;
    loadDailySummary();
  }

  // ============================================
  // Initialization
  // ============================================

  function init() {
    setDateDisplay();
    setupImageCapture();
    setupScreenObserver();

    // Load summary on initial page load if dashboard is active
    var dashboardScreen = document.getElementById('dashboard-screen');
    if (dashboardScreen && dashboardScreen.classList.contains('active')) {
      loadDailySummary();
    }
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
