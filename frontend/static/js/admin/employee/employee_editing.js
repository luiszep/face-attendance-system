// Employee Profile Editing JavaScript
let isEditMode = false;
let originalValues = {};

function toggleEditMode() {
  isEditMode = !isEditMode;
  
  if (isEditMode) {
    enterEditMode();
  } else {
    exitEditMode();
  }
}

function enterEditMode() {
  // Store original values
  originalValues = {
    firstName: document.getElementById('firstNameEdit').value,
    lastName: document.getElementById('lastNameEdit').value,
    occupation: document.getElementById('occupationEdit').value,
    regularWage: document.getElementById('regularWageEdit').value,
    overtimeWage: document.getElementById('overtimeWageEdit').value,
    regularHours: document.getElementById('regularHoursEdit').value,
    maxOvertime: document.getElementById('maxOvertimeEdit').value
  };
  
  // Hide display elements and show edit elements
  document.getElementById('firstNameDisplay').classList.add('hidden');
  document.getElementById('firstNameEdit').classList.remove('hidden');
  
  document.getElementById('lastNameDisplay').classList.add('hidden');
  document.getElementById('lastNameEdit').classList.remove('hidden');
  
  document.getElementById('occupationDisplay').classList.add('hidden');
  document.getElementById('occupationEdit').classList.remove('hidden');
  
  document.getElementById('regularWageDisplay').classList.add('hidden');
  document.getElementById('regularWageEditContainer').classList.remove('hidden');
  
  document.getElementById('overtimeWageDisplay').classList.add('hidden');
  document.getElementById('overtimeWageEditContainer').classList.remove('hidden');
  
  document.getElementById('regularHoursDisplay').classList.add('hidden');
  document.getElementById('regularHoursEditContainer').classList.remove('hidden');
  
  document.getElementById('maxOvertimeDisplay').classList.add('hidden');
  document.getElementById('maxOvertimeEditContainer').classList.remove('hidden');
  
  // Update buttons
  document.getElementById('editToggleBtn').classList.add('hidden');
  document.getElementById('editActions').classList.remove('hidden');
  document.getElementById('deleteBtn').classList.add('hidden');
  
  // Focus on first field
  document.getElementById('firstNameEdit').focus();
  
  // Setup validation for edit mode
  setupEditValidation();
}

function exitEditMode() {
  // Show display elements and hide edit elements
  document.getElementById('firstNameDisplay').classList.remove('hidden');
  document.getElementById('firstNameEdit').classList.add('hidden');
  
  document.getElementById('lastNameDisplay').classList.remove('hidden');
  document.getElementById('lastNameEdit').classList.add('hidden');
  
  document.getElementById('occupationDisplay').classList.remove('hidden');
  document.getElementById('occupationEdit').classList.add('hidden');
  
  document.getElementById('regularWageDisplay').classList.remove('hidden');
  document.getElementById('regularWageEditContainer').classList.add('hidden');
  
  document.getElementById('overtimeWageDisplay').classList.remove('hidden');
  document.getElementById('overtimeWageEditContainer').classList.add('hidden');
  
  document.getElementById('regularHoursDisplay').classList.remove('hidden');
  document.getElementById('regularHoursEditContainer').classList.add('hidden');
  
  document.getElementById('maxOvertimeDisplay').classList.remove('hidden');
  document.getElementById('maxOvertimeEditContainer').classList.add('hidden');
  
  // Update buttons
  document.getElementById('editToggleBtn').classList.remove('hidden');
  document.getElementById('editActions').classList.add('hidden');
  document.getElementById('deleteBtn').classList.remove('hidden');
}

function cancelEdit() {
  // Restore original values
  document.getElementById('firstNameEdit').value = originalValues.firstName;
  document.getElementById('lastNameEdit').value = originalValues.lastName;
  document.getElementById('occupationEdit').value = originalValues.occupation;
  document.getElementById('regularWageEdit').value = originalValues.regularWage;
  document.getElementById('overtimeWageEdit').value = originalValues.overtimeWage;
  document.getElementById('regularHoursEdit').value = originalValues.regularHours;
  document.getElementById('maxOvertimeEdit').value = originalValues.maxOvertime;
  
  isEditMode = false;
  exitEditMode();
}

// Validation state for edit form
let editValidationErrors = {
  firstName: false,
  lastName: false,
  occupation: false,
  regularWage: false,
  overtimeWage: false,
  regularHours: false,
  maxOvertime: false
};

function updateSaveButton() {
  const saveBtn = document.querySelector('button[onclick="saveChanges()"]');
  if (!saveBtn) return;
  
  const hasErrors = Object.values(editValidationErrors).some(error => error);
  
  if (hasErrors) {
    saveBtn.disabled = true;
    saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
    saveBtn.classList.remove('hover:bg-green-700', 'hover:shadow-xl', 'hover:-translate-y-0.5');
  } else {
    saveBtn.disabled = false;
    saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    saveBtn.classList.add('hover:bg-green-700', 'hover:shadow-xl', 'hover:-translate-y-0.5');
  }
}

function setupEditValidation() {
  // Text fields validation
  ['firstNameEdit', 'lastNameEdit', 'occupationEdit'].forEach(fieldId => {
    const field = document.getElementById(fieldId);
    if (!field) return;
    
    field.addEventListener('input', function() {
      const isValid = this.value.length <= 80 && this.value.trim().length > 0;
      const errorKey = fieldId.replace('Edit', '').replace('Name', '');
      editValidationErrors[fieldId.replace('Edit', '')] = !isValid;
      
      // Visual feedback
      if (!isValid) {
        this.classList.add('border-red-500');
        this.classList.remove('border-green-500/30');
      } else {
        this.classList.remove('border-red-500');
        this.classList.add('border-green-500/30');
      }
      
      updateSaveButton();
    });
  });

  // Wage fields validation
  ['regularWageEdit', 'overtimeWageEdit'].forEach(fieldId => {
    const field = document.getElementById(fieldId);
    if (!field) return;
    
    field.addEventListener('input', function() {
      const value = parseFloat(this.value);
      const isValid = value >= 0.01 && value <= 999.99;
      editValidationErrors[fieldId.replace('Edit', '')] = !isValid;
      
      // Visual feedback
      if (!isValid && this.value !== '') {
        this.classList.add('border-red-500');
        this.classList.remove('border-green-500/30');
      } else {
        this.classList.remove('border-red-500');
        this.classList.add('border-green-500/30');
      }
      
      updateSaveButton();
    });
  });

  // Hours fields validation
  const regularHoursField = document.getElementById('regularHoursEdit');
  const maxOvertimeField = document.getElementById('maxOvertimeEdit');
  
  if (regularHoursField) {
    regularHoursField.addEventListener('input', function() {
      const value = parseInt(this.value);
      const isValid = value >= 1 && value <= 24;
      editValidationErrors.regularHours = !isValid;
      
      // Visual feedback
      if (!isValid && this.value !== '') {
        this.classList.add('border-red-500');
        this.classList.remove('border-green-500/30');
      } else {
        this.classList.remove('border-red-500');
        this.classList.add('border-green-500/30');
      }
      
      updateSaveButton();
    });
  }
  
  if (maxOvertimeField) {
    maxOvertimeField.addEventListener('input', function() {
      const value = parseInt(this.value);
      const isValid = this.value === '' || (value >= 0 && value <= 24);
      editValidationErrors.maxOvertime = !isValid;
      
      // Visual feedback
      if (!isValid && this.value !== '') {
        this.classList.add('border-red-500');
        this.classList.remove('border-green-500/30');
      } else {
        this.classList.remove('border-red-500');
        this.classList.add('border-green-500/30');
      }
      
      updateSaveButton();
    });
  }
}

function saveChanges() {
  // Check if form is valid
  const hasErrors = Object.values(editValidationErrors).some(error => error);
  if (hasErrors) {
    alert('Please correct all validation errors before saving.');
    return;
  }
  
  // Validate required fields
  const firstName = document.getElementById('firstNameEdit').value.trim();
  const lastName = document.getElementById('lastNameEdit').value.trim();
  const occupation = document.getElementById('occupationEdit').value.trim();
  const regularWage = document.getElementById('regularWageEdit').value;
  const overtimeWage = document.getElementById('overtimeWageEdit').value;
  const regularHours = document.getElementById('regularHoursEdit').value;
  
  if (!firstName || !lastName || !occupation || !regularWage || !overtimeWage || !regularHours) {
    alert('Please fill in all required fields.');
    return;
  }
  
  // Set values in hidden form
  document.getElementById('hiddenFirstName').value = firstName;
  document.getElementById('hiddenLastName').value = lastName;
  document.getElementById('hiddenOccupation').value = occupation;
  document.getElementById('hiddenRegularWage').value = regularWage;
  document.getElementById('hiddenOvertimeWage').value = overtimeWage;
  document.getElementById('hiddenRegularHours').value = regularHours;
  document.getElementById('hiddenMaxOvertime').value = document.getElementById('maxOvertimeEdit').value;
  
  // Submit form
  document.getElementById('editEmployeeForm').submit();
}

// Auto-calculate overtime rate
document.addEventListener('DOMContentLoaded', function() {
  const regularWageEditField = document.getElementById('regularWageEdit');
  if (regularWageEditField) {
    regularWageEditField.addEventListener('input', function() {
      const regularWage = parseFloat(this.value);
      const overtimeWageInput = document.getElementById('overtimeWageEdit');
      
      if (regularWage && !overtimeWageInput.value) {
        overtimeWageInput.value = (regularWage * 1.5).toFixed(2);
      }
    });
  }
});