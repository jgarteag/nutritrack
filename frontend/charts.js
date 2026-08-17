/**
 * NutriTrack — Charts Module
 * Weekly bar chart and weight tracker with Chart.js.
 */
(function () {
  'use strict';

  // ============================================
  // Constants
  // ============================================
  var COLOR_GREEN = '#00d68f';
  var COLOR_RED = '#ff6b6b';
  var COLOR_GOAL_LINE = '#ff9f43';
  var COLOR_WEIGHT_LINE = '#00d68f';
  var COLOR_TEXT_SECONDARY = '#a0a0b0';
  var COLOR_GRID = '#2a2a4a';

  // ============================================
  // State
  // ============================================
  var weeklyChart = null;
  var weightChart = null;

  // ============================================
  // Helpers
  // ============================================

  /**
   * Get the Monday of the current week in YYYY-MM-DD format.
   */
  function getWeekStart() {
    var now = new Date();
    var day = now.getDay(); // 0=Sun, 1=Mon...
    var diff = day === 0 ? 6 : day - 1; // days since Monday
    var monday = new Date(now);
    monday.setDate(now.getDate() - diff);
    var year = monday.getFullYear();
    var month = String(monday.getMonth() + 1).padStart(2, '0');
    var d = String(monday.getDate()).padStart(2, '0');
    return year + '-' + month + '-' + d;
  }

  /**
   * Get short day label from a date string (e.g., "Mon").
   */
  function getDayLabel(dateStr) {
    var parts = dateStr.split('-');
    var d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    return d.toLocaleDateString('es-ES', { weekday: 'short' });
  }

  // ============================================
  // Weekly Bar Chart
  // ============================================

  /**
   * Fetch weekly summary data and render bar chart.
   */
  async function loadWeeklyChart() {
    var start = getWeekStart();

    try {
      var data = await window.NutriTrack.apiRequest('GET', '/summary/week?start=' + start);
      if (data && data.summaries) {
        renderWeeklyChart(data.summaries);
      }
    } catch (err) {
      console.error('Failed to load weekly data:', err.message);
    }
  }

  /**
   * Render the weekly bar chart with color-coded bars and goal line.
   */
  function renderWeeklyChart(summaries) {
    var canvas = document.getElementById('weekly-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    var labels = [];
    var calories = [];
    var colors = [];
    var goalValue = 0;

    // Process 7 days of data
    summaries.forEach(function (day) {
      labels.push(getDayLabel(day.date));
      calories.push(day.total_calories || 0);

      // Determine bar color based on status
      if (day.status === 'exceeded') {
        colors.push(COLOR_RED);
      } else {
        colors.push(COLOR_GREEN);
      }

      // Use the goal from any available day
      if (day.goal && day.goal.target_calories) {
        goalValue = day.goal.target_calories;
      }
    });

    // Destroy existing chart if present
    if (weeklyChart) {
      weeklyChart.destroy();
      weeklyChart = null;
    }

    var ctx = canvas.getContext('2d');

    // Build annotation plugin config for goal line
    var plugins = [];
    var annotationConfig = {};

    // Use chartjs-plugin-annotation if available, otherwise use a custom plugin
    var goalLinePlugin = {
      id: 'goalLine',
      afterDraw: function (chart) {
        if (goalValue <= 0) return;
        var yAxis = chart.scales.y;
        var ctx2 = chart.ctx;
        var yPixel = yAxis.getPixelForValue(goalValue);

        ctx2.save();
        ctx2.beginPath();
        ctx2.setLineDash([6, 4]);
        ctx2.strokeStyle = COLOR_GOAL_LINE;
        ctx2.lineWidth = 2;
        ctx2.moveTo(chart.chartArea.left, yPixel);
        ctx2.lineTo(chart.chartArea.right, yPixel);
        ctx2.stroke();
        ctx2.restore();
      }
    };

    weeklyChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Calorías',
          data: calories,
          backgroundColor: colors,
          borderRadius: 4,
          borderSkipped: false
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#16213e',
            titleColor: '#e8e8e8',
            bodyColor: '#e8e8e8',
            borderColor: '#2a2a4a',
            borderWidth: 1,
            callbacks: {
              label: function (context) {
                return context.parsed.y + ' kcal';
              }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: COLOR_TEXT_SECONDARY }
          },
          y: {
            beginAtZero: true,
            grid: { color: COLOR_GRID },
            ticks: {
              color: COLOR_TEXT_SECONDARY,
              callback: function (value) {
                return value + ' kcal';
              }
            }
          }
        }
      },
      plugins: [goalLinePlugin]
    });
  }

  // ============================================
  // Weight Line Chart
  // ============================================

  /**
   * Fetch weight history and render line chart.
   */
  async function loadWeightChart() {
    try {
      var data = await window.NutriTrack.apiRequest('GET', '/weight/history?limit=30');
      if (data && data.records) {
        renderWeightChart(data.records);
      }
    } catch (err) {
      console.error('Failed to load weight history:', err.message);
    }
  }

  /**
   * Render the weight line chart with bezier curves and gradient fill.
   */
  function renderWeightChart(records) {
    var canvas = document.getElementById('weight-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    // Sort records by date ascending
    var sorted = records.slice().sort(function (a, b) {
      return a.date.localeCompare(b.date);
    });

    var labels = sorted.map(function (r) {
      return getDayLabel(r.date) + ' ' + r.date.slice(8);
    });
    var weights = sorted.map(function (r) {
      return r.weight_kg;
    });

    // Destroy existing chart if present
    if (weightChart) {
      weightChart.destroy();
      weightChart = null;
    }

    var ctx = canvas.getContext('2d');

    // Create gradient fill
    var gradient = ctx.createLinearGradient(0, 0, 0, canvas.parentElement.clientHeight || 250);
    gradient.addColorStop(0, 'rgba(0, 214, 143, 0.3)');
    gradient.addColorStop(1, 'rgba(0, 214, 143, 0.0)');

    weightChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Peso (kg)',
          data: weights,
          borderColor: COLOR_WEIGHT_LINE,
          backgroundColor: gradient,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: COLOR_WEIGHT_LINE,
          pointBorderColor: COLOR_WEIGHT_LINE,
          pointRadius: 4,
          pointHoverRadius: 6,
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#16213e',
            titleColor: '#e8e8e8',
            bodyColor: '#e8e8e8',
            borderColor: '#2a2a4a',
            borderWidth: 1,
            callbacks: {
              label: function (context) {
                return context.parsed.y.toFixed(1) + ' kg';
              }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: COLOR_TEXT_SECONDARY }
          },
          y: {
            grid: { color: COLOR_GRID },
            ticks: {
              color: COLOR_TEXT_SECONDARY,
              callback: function (value) {
                return value + ' kg';
              }
            }
          }
        }
      }
    });
  }

  // ============================================
  // Weight Form Submission
  // ============================================

  /**
   * Set up the weight form submission handler.
   */
  function setupWeightForm() {
    var form = document.getElementById('weight-form');
    var errorEl = document.getElementById('weight-error');
    var submitBtn = document.getElementById('weight-submit-btn');

    if (!form) return;

    form.addEventListener('submit', async function (e) {
      e.preventDefault();

      var input = document.getElementById('weight-input');
      var weight = parseFloat(input.value);

      // Clear previous error
      if (errorEl) {
        errorEl.textContent = '';
        errorEl.style.display = 'none';
      }

      // Validate weight (30–300 kg)
      if (isNaN(weight) || weight < 30 || weight > 300) {
        showWeightError('Ingresa un peso válido entre 30 y 300 kg.');
        return;
      }

      // Disable button during submission
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Guardando...';
      }

      try {
        var response = await window.NutriTrack.apiRequest('POST', '/weight', {
          weight_kg: weight
        });

        if (response) {
          showWeightUpdateResult(response);
          // Clear input on success
          input.value = '';
        }
      } catch (err) {
        showWeightError(err.message || 'Error al guardar peso. Intenta de nuevo.');
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Registrar peso';
        }
      }
    });
  }

  /**
   * Display a weight form error message.
   */
  function showWeightError(message) {
    var errorEl = document.getElementById('weight-error');
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.style.display = 'block';
    }
  }

  /**
   * Show the weight update result panel with new TDEE and suggested goal.
   */
  function showWeightUpdateResult(response) {
    var resultEl = document.getElementById('weight-update-result');
    var tdeeEl = document.getElementById('weight-new-tdee');
    var goalEl = document.getElementById('weight-new-goal');

    if (!resultEl) return;

    // Display new TDEE and suggested goal
    if (tdeeEl) {
      tdeeEl.textContent = (response.new_tdee || '—') + ' kcal';
    }
    if (goalEl) {
      goalEl.textContent = (response.suggested_goal || '—') + ' kcal';
    }

    // Store the suggested goal for accept action
    resultEl.dataset.suggestedGoal = response.suggested_goal || '';

    // Show the result section
    resultEl.classList.add('visible');
  }

  /**
   * Hide the weight update result panel.
   */
  function hideWeightUpdateResult() {
    var resultEl = document.getElementById('weight-update-result');
    if (resultEl) {
      resultEl.classList.remove('visible');
    }
  }

  // ============================================
  // Accept / Keep Goal Logic
  // ============================================

  /**
   * Set up the accept and keep goal buttons.
   */
  function setupGoalButtons() {
    var acceptBtn = document.getElementById('weight-accept-goal');
    var keepBtn = document.getElementById('weight-keep-goal');

    if (acceptBtn) {
      acceptBtn.addEventListener('click', async function () {
        var resultEl = document.getElementById('weight-update-result');
        var suggestedGoal = resultEl ? parseInt(resultEl.dataset.suggestedGoal) : null;

        if (!suggestedGoal || isNaN(suggestedGoal)) {
          hideWeightUpdateResult();
          return;
        }

        acceptBtn.disabled = true;
        acceptBtn.textContent = 'Guardando...';

        try {
          await window.NutriTrack.apiRequest('PUT', '/profile/goal', {
            daily_calorie_goal: suggestedGoal
          });

          hideWeightUpdateResult();
          // Refresh the weight chart with updated data
          await loadWeightChart();
        } catch (err) {
          showWeightError(err.message || 'Error al actualizar meta.');
        } finally {
          acceptBtn.disabled = false;
          acceptBtn.textContent = 'Aceptar';
        }
      });
    }

    if (keepBtn) {
      keepBtn.addEventListener('click', function () {
        hideWeightUpdateResult();
      });
    }
  }

  // ============================================
  // Screen Visibility Observers
  // ============================================

  /**
   * Set up MutationObservers to detect screen visibility changes
   * and refresh charts accordingly.
   */
  function setupScreenObservers() {
    var weeklyScreen = document.getElementById('weekly-screen');
    var weightScreen = document.getElementById('weight-screen');

    if (weeklyScreen) {
      var weeklyObserver = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
          if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
            if (weeklyScreen.classList.contains('active')) {
              loadWeeklyChart();
            }
          }
        });
      });
      weeklyObserver.observe(weeklyScreen, { attributes: true });
    }

    if (weightScreen) {
      var weightObserver = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
          if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
            if (weightScreen.classList.contains('active')) {
              loadWeightChart();
            }
          }
        });
      });
      weightObserver.observe(weightScreen, { attributes: true });
    }
  }

  // ============================================
  // Initialization
  // ============================================

  function init() {
    setupWeightForm();
    setupGoalButtons();
    setupScreenObservers();
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
