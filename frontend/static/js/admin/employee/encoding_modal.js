// Employee Database Overview JavaScript - Encoding Modal and Navigation

// Encoding Generation Functionality
let isEncodingInProgress = false;

function startEncodingGeneration() {
  // Show confirmation dialog first
  if (!confirm('This will generate face encodings for all employees. The process may take 1-2 minutes. Are you sure you want to continue?')) {
    return;
  }
  
  // Set encoding in progress flag
  isEncodingInProgress = true;
  
  // Show toast notification that encoding has started
  if (window.parent && window.parent.showNotification) {
    window.parent.showNotification("Encoding generation started. Please do not close this tab.", "info", 3000);
  } else if (window.showNotification) {
    window.showNotification("Encoding generation started. Please do not close this tab.", "info", 3000);
  }
  
  // Show the modal
  document.getElementById('encodingModal').classList.remove('hidden');
  
  // Prevent page closing/navigation
  setupPageProtection();
  
  // Start the animated progress simulation
  startProgressAnimation();
  
  // Submit the form to start actual encoding
  setTimeout(() => {
    document.getElementById('encodingForm').submit();
  }, 1000); // Small delay to ensure modal is visible
}

function setupPageProtection() {
  // Prevent back button
  history.pushState(null, null, location.href);
  window.addEventListener('popstate', function() {
    if (isEncodingInProgress) {
      history.pushState(null, null, location.href);
      // Show custom alert instead of browser dialog
      showCustomAlert('Encoding generation is in progress. Please wait for completion before navigating away.');
    }
  });
  
  // Disable all navigation elements during encoding
  disableNavigation();
}

function disableNavigation() {
  // Disable all links temporarily
  const links = document.querySelectorAll('a, button[onclick*="location"], button[onclick*="window"]');
  links.forEach(link => {
    if (link.onclick && !link.onclick.toString().includes('startEncodingGeneration')) {
      link.dataset.originalOnclick = link.onclick.toString();
      link.onclick = function(e) {
        e.preventDefault();
        showCustomAlert('Please wait for encoding generation to complete before navigating.');
        return false;
      };
    }
    if (link.href && !link.href.includes('javascript:')) {
      link.dataset.originalHref = link.href;
      link.href = 'javascript:void(0)';
      link.onclick = function(e) {
        e.preventDefault();
        showCustomAlert('Please wait for encoding generation to complete before navigating.');
        return false;
      };
    }
  });
  
  // Disable form submissions (except encoding form)
  const forms = document.querySelectorAll('form:not(#encodingForm)');
  forms.forEach(form => {
    form.addEventListener('submit', function(e) {
      if (isEncodingInProgress) {
        e.preventDefault();
        showCustomAlert('Please wait for encoding generation to complete before submitting forms.');
      }
    });
  });
}

function enableNavigation() {
  // Re-enable all links
  const links = document.querySelectorAll('a, button[onclick*="location"], button[onclick*="window"]');
  links.forEach(link => {
    if (link.dataset.originalOnclick) {
      link.onclick = new Function(link.dataset.originalOnclick);
      delete link.dataset.originalOnclick;
    }
    if (link.dataset.originalHref) {
      link.href = link.dataset.originalHref;
      link.onclick = null;
      delete link.dataset.originalHref;
    }
  });
}

function showCustomAlert(message) {
  // Create custom alert modal
  const alertModal = document.createElement('div');
  alertModal.id = 'customAlert';
  alertModal.className = 'fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center';
  alertModal.innerHTML = `
    <div class="bg-gray-900 rounded-2xl shadow-2xl border-4 border-amber-400 max-w-md w-full mx-4 p-6 text-center">
      <div class="bg-amber-500/20 rounded-full p-3 w-16 h-16 mx-auto mb-4 flex items-center justify-center">
        <svg class="w-8 h-8 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 15.5c-.77.833.192 2.5 1.732 2.5z"></path>
        </svg>
      </div>
      <h3 class="text-xl font-bold text-white mb-3">Please Wait</h3>
      <p class="text-gray-300 mb-6">${message}</p>
      <button onclick="closeCustomAlert()" class="bg-amber-500 hover:bg-amber-600 text-black px-6 py-2 rounded-full font-semibold transition-colors">
        OK
      </button>
    </div>
  `;
  
  document.body.appendChild(alertModal);
  
  // Auto-close after 3 seconds
  setTimeout(() => {
    closeCustomAlert();
  }, 3000);
}

function closeCustomAlert() {
  const alertModal = document.getElementById('customAlert');
  if (alertModal) {
    alertModal.remove();
  }
}

function startProgressAnimation() {
  const steps = [
    { selector: 'step1', delay: 500 },
    { selector: 'step2', delay: 2000 },
    { selector: 'step3', delay: 5000 },
    { selector: 'step4', delay: 8000 }
  ];
  
  // Simulate progress steps
  setTimeout(() => updateProgressStep(1), 500);
  setTimeout(() => updateProgressStep(2), 3000);
  setTimeout(() => updateProgressStep(3), 8000);
  setTimeout(() => updateProgressStep(4), 12000);
}

function updateProgressStep(step) {
  const steps = document.querySelectorAll('.progress-step');
  if (steps[step - 1]) {
    const spinner = steps[step - 1].querySelector('.animate-spin, .border-gray-500');
    const checkmark = steps[step - 1].querySelector('.w-4.h-4:last-child');
    
    if (spinner && checkmark) {
      // Replace spinner with checkmark
      spinner.outerHTML = `
        <svg class="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
      `;
      
      // Update text color
      steps[step - 1].classList.remove('text-gray-500');
      steps[step - 1].classList.add('text-gray-300');
    }
  }
  
  // Update next step if it exists
  if (step < 4 && steps[step]) {
    const nextSpinner = steps[step].querySelector('.border-gray-500');
    if (nextSpinner) {
      nextSpinner.classList.remove('border-gray-500');
      nextSpinner.classList.add('border-green-400', 'border-t-transparent', 'animate-spin');
    }
    steps[step].classList.remove('text-gray-500');
    steps[step].classList.add('text-gray-400');
  }
}

// Clean up on page load (in case of refresh during encoding)
window.addEventListener('load', function() {
  // Reset modal state
  const encodingModal = document.getElementById('encodingModal');
  if (encodingModal) {
    encodingModal.classList.add('hidden');
  }
  isEncodingInProgress = false;
  
  // Re-enable navigation in case of page refresh during encoding
  enableNavigation();
});

// Handle encoding completion (this would be triggered by server response)
function completeEncoding(success = true) {
  isEncodingInProgress = false;
  
  // Re-enable navigation
  enableNavigation();
  
  // Close the modal immediately
  closeModal();
  
  // Show toast notification instead of modal completion screen
  if (success) {
    // Check if parent window has the notification function
    if (window.parent && window.parent.showNotification) {
      window.parent.showNotification("Encodings generated successfully! Face recognition is now ready for all employees.", "success", 7000);
    } else if (window.showNotification) {
      window.showNotification("Encodings generated successfully! Face recognition is now ready for all employees.", "success", 7000);
    }
  } else {
    if (window.parent && window.parent.showNotification) {
      window.parent.showNotification("Encoding generation failed. Please try again or contact support.", "error", 7000);
    } else if (window.showNotification) {
      window.showNotification("Encoding generation failed. Please try again or contact support.", "error", 7000);
    }
  }
}

function closeModal() {
  const encodingModal = document.getElementById('encodingModal');
  if (encodingModal) {
    encodingModal.classList.add('hidden');
  }
  // Refresh page to show updated status
  window.location.reload();
}