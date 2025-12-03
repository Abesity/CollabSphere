// FAQ Functionality
document.addEventListener('DOMContentLoaded', function() {
    const faqCategories = document.querySelectorAll('.faq-category');
    const faqItems = document.querySelectorAll('.faq-item');
    const searchInput = document.getElementById('searchInput');
    const noResults = document.getElementById('noResults');
    const faqContent = document.querySelector('.faq-content');

    // Toggle Category Dropdown
    faqCategories.forEach(category => {
        const categoryHeader = category.querySelector('.category-header');
        
        categoryHeader.addEventListener('click', () => {
            category.classList.toggle('collapsed');
        });
    });

    // Toggle FAQ Item answers
    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        
        question.addEventListener('click', () => {
            const isActive = item.classList.contains('active');
            
            // Close all other items in the same category
            const parentCategory = item.closest('.faq-category');
            const categoryItems = parentCategory.querySelectorAll('.faq-item');
            
            categoryItems.forEach(otherItem => {
                if (otherItem !== item) {
                    otherItem.classList.remove('active');
                }
            });
            
            // Toggle current item
            if (isActive) {
                item.classList.remove('active');
            } else {
                item.classList.add('active');
            }
        });
    });

    // Search functionality
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase().trim();
        let hasResults = false;

        if (searchTerm === '') {
            // Reset everything when search is empty
            faqItems.forEach(item => {
                item.classList.remove('hidden');
                item.classList.remove('active');
                const question = item.querySelector('.faq-question h3');
                const answer = item.querySelector('.faq-answer p');
                question.innerHTML = question.textContent;
                answer.innerHTML = answer.textContent;
            });

            faqCategories.forEach(category => {
                category.style.display = 'block';
                category.classList.remove('collapsed');
            });

            noResults.style.display = 'none';
            faqContent.style.display = 'block';
            return;
        }

        // Search through all items
        faqItems.forEach(item => {
            const question = item.querySelector('.faq-question h3');
            const answer = item.querySelector('.faq-answer p');
            const questionText = question.textContent.toLowerCase();
            const answerText = answer.textContent.toLowerCase();

            // Remove previous highlights
            question.innerHTML = question.textContent;
            answer.innerHTML = answer.textContent;

            if (questionText.includes(searchTerm) || answerText.includes(searchTerm)) {
                item.classList.remove('hidden');
                item.classList.add('active');
                hasResults = true;

                // Highlight search term
                if (questionText.includes(searchTerm)) {
                    question.innerHTML = highlightText(question.textContent, searchTerm);
                }
                if (answerText.includes(searchTerm)) {
                    answer.innerHTML = highlightText(answer.textContent, searchTerm);
                }
            } else {
                item.classList.add('hidden');
                item.classList.remove('active');
            }
        });

        // Show/hide categories based on visible items and expand them
        faqCategories.forEach(category => {
            const visibleItems = category.querySelectorAll('.faq-item:not(.hidden)');
            if (visibleItems.length === 0) {
                category.style.display = 'none';
            } else {
                category.style.display = 'block';
                category.classList.remove('collapsed'); // Expand categories with results
            }
        });

        // Show/hide no results message
        if (hasResults) {
            noResults.style.display = 'none';
            faqContent.style.display = 'block';
        } else {
            noResults.style.display = 'block';
            faqContent.style.display = 'none';
        }
    });

    // Function to highlight search terms
    function highlightText(text, searchTerm) {
        const regex = new RegExp(`(${escapeRegex(searchTerm)})`, 'gi');
        return text.replace(regex, '<span class="highlight">$1</span>');
    }

    // Escape special regex characters
    function escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // Clear search on escape key
    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            this.value = '';
            this.dispatchEvent(new Event('input'));
            this.blur();
        }
    });

    // Expand all categories by default on page load
    faqCategories.forEach(category => {
        category.classList.remove('collapsed');
    });
});