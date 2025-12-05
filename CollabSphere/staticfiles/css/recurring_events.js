// ============================================
// TASK 3.2.1: Front-end Logic for Recurring Event Options
// ============================================

document.addEventListener('DOMContentLoaded', function() {
  
  // Get all the elements
  const isRecurringCheckbox = document.getElementById('isRecurring');
  const recurringOptions = document.getElementById('recurringOptions');
  const frequencySelect = document.getElementById('frequency');
  const weeklyOptions = document.getElementById('weeklyOptions');
  const endsOnSelect = document.getElementById('endsOn');
  const endDateField = document.getElementById('endDateField');
  const occurrencesField = document.getElementById('occurrencesField');
  const recurrenceSummary = document.getElementById('recurrenceSummary');
  const summaryText = document.getElementById('summaryText');

  // Check if elements exist before attaching event listeners
  if (!isRecurringCheckbox) {
    console.log('Recurring event elements not found on this page');
    return;
  }

  // 1. Toggle recurring options visibility when checkbox is clicked
  isRecurringCheckbox.addEventListener('change', function() {
    if (this.checked) {
      recurringOptions.style.display = 'block';
      // Set default frequency
      if (!frequencySelect.value) {
        frequencySelect.value = 'weekly';
        toggleWeeklyOptions();
      }
    } else {
      recurringOptions.style.display = 'none';
      // Reset all recurring fields
      resetRecurringFields();
    }
    updateSummary();
  });

  // 2. Show/hide weekly day selector based on frequency
  frequencySelect.addEventListener('change', function() {
    toggleWeeklyOptions();
    updateSummary();
  });

  function toggleWeeklyOptions() {
    if (frequencySelect.value === 'weekly') {
      weeklyOptions.style.display = 'block';
    } else {
      weeklyOptions.style.display = 'none';
      // Uncheck all days when hiding
      const dayCheckboxes = weeklyOptions.querySelectorAll('input[type="checkbox"]');
      dayCheckboxes.forEach(cb => cb.checked = false);
    }
  }

  // 3. Show/hide end date or occurrences fields based on "Ends" selection
  endsOnSelect.addEventListener('change', function() {
    const selectedValue = this.value;
    
    // Hide all fields first
    endDateField.style.display = 'none';
    occurrencesField.style.display = 'none';
    
    // Show the appropriate field
    if (selectedValue === 'on') {
      endDateField.style.display = 'block';
    } else if (selectedValue === 'after') {
      occurrencesField.style.display = 'block';
    }
    
    updateSummary();
  });

  // 4. Update summary when any recurring option changes
  const allRecurringInputs = recurringOptions.querySelectorAll('input, select');
  allRecurringInputs.forEach(input => {
    input.addEventListener('change', updateSummary);
  });

  // 5. Generate human-readable summary
  function updateSummary() {
    if (!isRecurringCheckbox.checked) {
      recurrenceSummary.style.display = 'none';
      return;
    }

    const frequency = frequencySelect.value;
    const endsOn = endsOnSelect.value;
    let summary = '';

    // Build frequency text
    if (frequency === 'daily') {
      summary = 'Repeats every day';
    } else if (frequency === 'weekly') {
      const selectedDays = getSelectedDays();
      if (selectedDays.length > 0) {
        summary = `Repeats every week on ${selectedDays.join(', ')}`;
      } else {
        summary = 'Repeats weekly (select days)';
      }
    } else if (frequency === 'monthly') {
      summary = 'Repeats every month';
    } else if (frequency === 'yearly') {
      summary = 'Repeats every year';
    } else {
      summary = 'Select a frequency';
    }

    // Add end condition
    if (endsOn === 'never') {
      summary += ', never ends';
    } else if (endsOn === 'on') {
      const endDate = document.getElementById('recurrenceEndDate').value;
      if (endDate) {
        summary += `, until ${formatDate(endDate)}`;
      } else {
        summary += ', until (select date)';
      }
    } else if (endsOn === 'after') {
      const occurrences = document.getElementById('occurrences').value;
      summary += `, for ${occurrences} occurrence${occurrences > 1 ? 's' : ''}`;
    }

    summaryText.textContent = summary;
    recurrenceSummary.style.display = frequency ? 'block' : 'none';
  }

  // 6. Helper: Get selected days as text
  function getSelectedDays() {
    const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const selectedDays = [];
    
    const dayCheckboxes = weeklyOptions.querySelectorAll('input[type="checkbox"]:checked');
    dayCheckboxes.forEach(checkbox => {
      const dayIndex = parseInt(checkbox.value);
      selectedDays.push(dayNames[dayIndex]);
    });
    
    return selectedDays;
  }

  // 7. Helper: Format date to readable format
  function formatDate(dateString) {
    const date = new Date(dateString);
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    return date.toLocaleDateString('en-US', options);
  }

  // 8. Reset all recurring fields
  function resetRecurringFields() {
    frequencySelect.value = '';
    endsOnSelect.value = 'never';
    document.getElementById('recurrenceEndDate').value = '';
    document.getElementById('occurrences').value = '10';
    
    // Uncheck all days
    const dayCheckboxes = weeklyOptions.querySelectorAll('input[type="checkbox"]');
    dayCheckboxes.forEach(cb => cb.checked = false);
    
    // Hide all conditional fields
    weeklyOptions.style.display = 'none';
    endDateField.style.display = 'none';
    occurrencesField.style.display = 'none';
    recurrenceSummary.style.display = 'none';
  }

  // 9. Form validation before submit
  const eventForm = document.getElementById('eventForm');
  if (eventForm) {
    eventForm.addEventListener('submit', function(e) {
      if (isRecurringCheckbox.checked) {
        // Validate frequency is selected
        if (!frequencySelect.value) {
          e.preventDefault();
          alert('Please select a recurrence frequency.');
          return false;
        }

        // Validate weekly days are selected
        if (frequencySelect.value === 'weekly') {
          const selectedDays = weeklyOptions.querySelectorAll('input[type="checkbox"]:checked');
          if (selectedDays.length === 0) {
            e.preventDefault();
            alert('Please select at least one day for weekly recurrence.');
            return false;
          }
        }

        // Validate end date is set
        if (endsOnSelect.value === 'on') {
          const endDate = document.getElementById('recurrenceEndDate').value;
          if (!endDate) {
            e.preventDefault();
            alert('Please select an end date.');
            return false;
          }

          // Check end date is after start date
          const startDate = document.getElementById('eventStartDate').value;
          if (startDate && endDate < startDate.split('T')[0]) {
            e.preventDefault();
            alert('End date must be after the start date.');
            return false;
          }
        }

        // Validate occurrences is set
        if (endsOnSelect.value === 'after') {
          const occurrences = document.getElementById('occurrences').value;
          if (!occurrences || occurrences < 1) {
            e.preventDefault();
            alert('Please enter a valid number of occurrences.');
            return false;
          }
        }
      }
      
      return true;
    });
  }

  // 10. Initialize on modal show (if using Bootstrap modal)
  const eventModal = document.getElementById('newEventModal');
  if (eventModal) {
    eventModal.addEventListener('shown.bs.modal', function() {
      // Reset form when modal opens
      if (eventForm) {
        eventForm.reset();
        resetRecurringFields();
        recurringOptions.style.display = 'none';
      }
    });
  }

});

// ============================================
// Additional Utility Functions
// ============================================

// Function to pre-populate form for editing existing recurring event
function loadRecurringEventData(eventData) {
  if (eventData.is_recurring) {
    document.getElementById('isRecurring').checked = true;
    document.getElementById('recurringOptions').style.display = 'block';
    
    if (eventData.frequency) {
      document.getElementById('frequency').value = eventData.frequency;
    }
    
    if (eventData.recurrence_days && eventData.recurrence_days.length > 0) {
      eventData.recurrence_days.forEach(day => {
        const checkbox = document.querySelector(`input[name="days[]"][value="${day}"]`);
        if (checkbox) checkbox.checked = true;
      });
      document.getElementById('weeklyOptions').style.display = 'block';
    }
    
    if (eventData.recurrence_end_type) {
      document.getElementById('endsOn').value = eventData.recurrence_end_type;
      
      if (eventData.recurrence_end_type === 'on' && eventData.recurrence_end_date) {
        document.getElementById('recurrenceEndDate').value = eventData.recurrence_end_date;
        document.getElementById('endDateField').style.display = 'block';
      } else if (eventData.recurrence_end_type === 'after' && eventData.recurrence_occurrences) {
        document.getElementById('occurrences').value = eventData.recurrence_occurrences;
        document.getElementById('occurrencesField').style.display = 'block';
      }
    }
  }
}