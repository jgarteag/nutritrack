/**
 * NutriTrack — Onboarding Flow
 * Multi-step form: weight/height → age/sex → activity level → TDEE result & goal.
 */
(function () {
  'use strict';

  // ============================================
  // State
  // ============================================
  var currentStep = 1;
  var totalSteps = 4;
  var onboardingData = {
    weight_kg: null,
    height_cm: null,
    age: null,
    sex: null,
    activity_level: null
  };
  var suggestedGoal = null;
  var calculatedTdee = null;

  // ============================================
  // Validation Rules
  // ============================================
  var VALIDATION = {
    weight: { min: 30, max: 300, label: 'Peso' },
    height: { min: 100, max: 250, label: 'Altura' },
    age: { min: 13, max: 120, label: 'Edad' }
  };

  // ============================================
  // Helpers
  // ============================================

  function showError(message) {
    var errorEl = document.getElementById('onboarding-error');
    if (errorEl) {
      errorEl.textContent = message;
      errorEl.style.display = 'block';
    }
  }

  function clearError() {
    var errorEl = document.getElementById('onboarding-error');
    if (errorEl) {
      errorEl.textContent = '';
      errorEl.style.display = 'none';
    }
  }

  function validateRange(value, rule) {
    if (value === null || value === '' || isNaN(value)) {
      return rule.label + ' es requerido.';
    }
    var num = parseFloat(value);
    if (num < rule.min || num > rule.max) {
      return rule.label + ' debe estar entre ' + rule.min + ' y ' + rule.max + '.';
    }
    return null;
  }

  // ============================================
  // Step Navigation
  // ============================================

  function goToStep(step) {
    if (step < 1 || step > totalSteps) return;

    // Hide current step
    var currentStepEl = document.getElementById('onboarding-step-' + currentStep);
    if (currentStepEl) {
      currentStepEl.classList.remove('active');
    }

    // Show target step
    var targetStepEl = document.getElementById('onboarding-step-' + step);
    if (targetStepEl) {
      targetStepEl.classList.add('active');
    }

    // Update step dots
    var dots = document.querySelectorAll('.step-dot');
    dots.forEach(function (dot, index) {
      if (index < step) {
        dot.classList.add('active');
      } else {
        dot.classList.remove('active');
      }
    });

    currentStep = step;
    clearError();
  }

  // ============================================
  // Step 1: Weight & Height
  // ============================================

  function validateStep1() {
    var weightInput = document.getElementById('onboarding-weight');
    var heightInput = document.getElementById('onboarding-height');

    var weightVal = weightInput ? weightInput.value : '';
    var heightVal = heightInput ? heightInput.value : '';

    var weightError = validateRange(weightVal, VALIDATION.weight);
    if (weightError) {
      showError(weightError);
      return false;
    }

    var heightError = validateRange(heightVal, VALIDATION.height);
    if (heightError) {
      showError(heightError);
      return false;
    }

    onboardingData.weight_kg = parseFloat(weightVal);
    onboardingData.height_cm = parseFloat(heightVal);
    return true;
  }

  // ============================================
  // Step 2: Age & Sex
  // ============================================

  function validateStep2() {
    var ageInput = document.getElementById('onboarding-age');
    var sexInput = document.getElementById('onboarding-sex');

    var ageVal = ageInput ? ageInput.value : '';
    var sexVal = sexInput ? sexInput.value : '';

    var ageError = validateRange(ageVal, VALIDATION.age);
    if (ageError) {
      showError(ageError);
      return false;
    }

    if (!sexVal) {
      showError('Por favor selecciona tu sexo.');
      return false;
    }

    onboardingData.age = parseInt(ageVal, 10);
    onboardingData.sex = sexVal;
    return true;
  }

  // ============================================
  // Step 3: Activity Level → POST /profile
  // ============================================

  function validateStep3() {
    var activityInput = document.getElementById('onboarding-activity');
    var activityVal = activityInput ? activityInput.value : '';

    if (!activityVal) {
      showError('Por favor selecciona tu nivel de actividad.');
      return false;
    }

    onboardingData.activity_level = activityVal;
    return true;
  }

  async function submitProfile() {
    var btn = document.getElementById('onboarding-next-3');
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Calculando...';
    }

    try {
      var result = await window.NutriTrack.apiRequest('POST', '/profile', onboardingData);

      calculatedTdee = result.tdee;
      suggestedGoal = result.suggested_goal;

      // Display TDEE and goal
      var tdeeDisplay = document.getElementById('tdee-display');
      var goalDisplay = document.getElementById('goal-display');

      if (tdeeDisplay) tdeeDisplay.textContent = calculatedTdee;
      if (goalDisplay) goalDisplay.textContent = suggestedGoal;

      // Move to step 4
      goToStep(4);
    } catch (err) {
      showError(err.message || 'Error al crear perfil. Intenta de nuevo.');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Calcular TDEE';
      }
    }
  }

  // ============================================
  // Step 4: Accept/Adjust Goal → Navigate to Dashboard
  // ============================================

  async function confirmGoal() {
    var adjustInput = document.getElementById('onboarding-goal-adjust');
    var adjustedGoal = adjustInput ? adjustInput.value.trim() : '';
    var btn = document.getElementById('onboarding-confirm');

    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Comenzando...';
    }

    try {
      // If user adjusted the goal, PUT the new value
      if (adjustedGoal && parseInt(adjustedGoal, 10) !== suggestedGoal) {
        var goalValue = parseInt(adjustedGoal, 10);
        if (isNaN(goalValue) || goalValue < 1200 || goalValue > 10000) {
          showError('La meta debe estar entre 1200 y 10000 kcal.');
          return;
        }
        await window.NutriTrack.apiRequest('PUT', '/profile/goal', {
          daily_calorie_goal: goalValue
        });
      }

      // Show nav bar and navigate to dashboard
      var navBar = document.getElementById('nav-bar');
      if (navBar) navBar.classList.add('visible');

      window.NutriTrack.navigateToScreen('dashboard-screen', 'left');
    } catch (err) {
      showError(err.message || 'Error al establecer meta. Intenta de nuevo.');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Comenzar';
      }
    }
  }

  // ============================================
  // Event Listeners
  // ============================================

  function setupOnboarding() {
    // Step 1 → Step 2
    var next1 = document.getElementById('onboarding-next-1');
    if (next1) {
      next1.addEventListener('click', function () {
        clearError();
        if (validateStep1()) {
          goToStep(2);
        }
      });
    }

    // Step 2 → Step 3
    var next2 = document.getElementById('onboarding-next-2');
    if (next2) {
      next2.addEventListener('click', function () {
        clearError();
        if (validateStep2()) {
          goToStep(3);
        }
      });
    }

    // Step 3 → Submit profile and show TDEE
    var next3 = document.getElementById('onboarding-next-3');
    if (next3) {
      next3.addEventListener('click', function () {
        clearError();
        if (validateStep3()) {
          submitProfile();
        }
      });
    }

    // Step 4 → Confirm goal and go to dashboard
    var confirmBtn = document.getElementById('onboarding-confirm');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', function () {
        clearError();
        confirmGoal();
      });
    }
  }

  // ============================================
  // Initialization
  // ============================================

  function init() {
    setupOnboarding();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
