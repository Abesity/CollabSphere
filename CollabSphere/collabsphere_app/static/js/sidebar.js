document.addEventListener('DOMContentLoaded', function() {
  const sidebarNav = document.getElementById('sidebar-nav');
  const sidebarLinks = document.querySelectorAll('.sidebar-link');
  
  
  const blueBgClass = 'sidebar-blue-bg'; 
  
  sidebarLinks.forEach(link => {
    link.addEventListener('click', function(event) {
      
      sidebarNav.classList.add(blueBgClass);

      sidebarLinks.forEach(item => {
        item.classList.remove('active');
      });
      event.currentTarget.classList.add('active');
    });
  });
});