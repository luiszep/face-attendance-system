// Enhanced JavaScript for Employee Form - Image Preview and Validation
document.addEventListener('DOMContentLoaded', function() {
    const imageInput = document.getElementById('image');
    const photoPreview = document.getElementById('photoPreview');
    const regIdInput = document.getElementById('reg_id');
    const imageError = document.getElementById('imageError');

    // Image preview functionality
    imageInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = function(e) {
                photoPreview.innerHTML = `
                    <div class="relative w-full h-full">
                        <img src="${e.target.result}" alt="Employee Photo" class="w-full h-full object-cover rounded-lg">
                        <div class="absolute inset-0 bg-black bg-opacity-0 hover:bg-opacity-10 transition-all rounded-lg flex items-center justify-center">
                            <span class="text-white opacity-0 hover:opacity-100 transition-opacity">Click to change</span>
                        </div>
                    </div>
                `;
            };
            reader.readAsDataURL(file);
            
            // Validate filename
            validateImageFilename(file.name, regIdInput.value);
        }
    });

    // Real-time filename validation
    regIdInput.addEventListener('input', function() {
        if (imageInput.files[0]) {
            validateImageFilename(imageInput.files[0].name, this.value);
        }
    });

    function validateImageFilename(filename, regId) {
        if (!regId) return;
        
        const expectedFilename = regId.toUpperCase() + '.jpg';
        if (filename !== expectedFilename) {
            imageError.textContent = `Filename should be: ${expectedFilename}`;
            imageError.classList.remove('hidden');
        } else {
            imageError.classList.add('hidden');
        }
    }

    // Form enhancement - auto-calculate overtime rate
    const regularWageInput = document.getElementById('regular_wage');
    const overtimeWageInput = document.getElementById('overtime_wage');
    
    regularWageInput.addEventListener('input', function() {
        if (this.value && !overtimeWageInput.value) {
            overtimeWageInput.value = (parseFloat(this.value) * 1.5).toFixed(2);
        }
    });

    // Validation state tracking
    let validationErrors = {
        first_name: false,
        last_name: false,
        occupation: false,
        reg_id: false,
        regular_wage: false,
        overtime_wage: false,
        regular_hours: false,
        maximum_overtime_hours: false
    };

    // Update submit button state based on validation
    function updateSubmitButton() {
        const submitBtn = document.getElementById('submitBtn');
        const hasErrors = Object.values(validationErrors).some(error => error);
        
        if (hasErrors) {
            submitBtn.disabled = true;
            submitBtn.classList.add('opacity-50', 'cursor-not-allowed');
            submitBtn.classList.remove('hover:bg-green-600', 'hover:shadow-xl', 'hover:-translate-y-0.5');
        } else {
            submitBtn.disabled = false;
            submitBtn.classList.remove('opacity-50', 'cursor-not-allowed');
            submitBtn.classList.add('hover:bg-green-600', 'hover:shadow-xl', 'hover:-translate-y-0.5');
        }
    }

    // Real-time validation feedback with enforcement
    function addValidationFeedback() {
        // Text field validation (minimal visual feedback)
        ['first_name', 'last_name', 'occupation', 'reg_id'].forEach(fieldId => {
            const field = document.getElementById(fieldId);
            
            field.addEventListener('input', function() {
                const isValid = this.value.length <= 80 && this.value.trim().length > 0;
                validationErrors[fieldId] = !isValid;
                
                // Simple visual feedback - red border for invalid
                if (!isValid) {
                    this.classList.add('border-red-500');
                    this.classList.remove('border-green-500/30');
                } else {
                    this.classList.remove('border-red-500');
                    this.classList.add('border-green-500/30');
                }
                
                updateSubmitButton();
            });
        });

        // Wage validation (minimal visual feedback)
        [regularWageInput, overtimeWageInput].forEach(field => {
            field.addEventListener('input', function() {
                const value = parseFloat(this.value);
                const fieldId = this.id;
                const isValid = value >= 0.01 && value <= 999.99;
                validationErrors[fieldId] = !isValid;
                
                // Simple visual feedback - red border for invalid
                if (!isValid && this.value !== '') {
                    this.classList.add('border-red-500');
                    this.classList.remove('border-green-500/30');
                } else {
                    this.classList.remove('border-red-500');
                    this.classList.add('border-green-500/30');
                }
                
                updateSubmitButton();
            });
        });

        // Hours validation (minimal visual feedback)
        const regularHoursInput = document.getElementById('regular_hours');
        const maxOvertimeInput = document.getElementById('maximum_overtime_hours');
        
        [regularHoursInput, maxOvertimeInput].forEach(field => {
            field.addEventListener('input', function() {
                const value = parseInt(this.value);
                const fieldId = this.id;
                const isRegular = fieldId === 'regular_hours';
                const min = isRegular ? 1 : 0;
                const max = 24;
                const isOptional = fieldId === 'maximum_overtime_hours';
                
                // For optional field, empty value is valid
                const isValid = isOptional ? (this.value === '' || (value >= min && value <= max)) : (value >= min && value <= max);
                validationErrors[fieldId] = !isValid;
                
                // Simple visual feedback - red border for invalid
                if (!isValid && this.value !== '') {
                    this.classList.add('border-red-500');
                    this.classList.remove('border-green-500/30');
                } else {
                    this.classList.remove('border-red-500');
                    this.classList.add('border-green-500/30');
                }
                
                updateSubmitButton();
            });
        });
    }
    
    // Initialize validation feedback
    addValidationFeedback();
});