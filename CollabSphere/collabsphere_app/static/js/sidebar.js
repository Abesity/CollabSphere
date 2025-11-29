document.addEventListener('DOMContentLoaded', function() {
  const sidebarNav = document.getElementById('sidebar-nav');
  const sidebarLinks = document.querySelectorAll('.sidebar-link');
  const sidebarToggle = document.querySelector('.sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  const sidebarOverlay = document.querySelector('.sidebar-overlay');
  
  const blueBgClass = 'sidebar-blue-bg';
  
  sidebarLinks.forEach(link => {
    link.addEventListener('click', function(event) {
      sidebarNav.classList.add(blueBgClass);

      sidebarLinks.forEach(item => {
        item.classList.remove('active');
      });
      event.currentTarget.classList.add('active');
      
      if (window.innerWidth < 768) {
        sidebar?.classList.remove('show');
        sidebarOverlay?.classList.remove('show');
      }
    });
  });

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', function() {
      sidebar.classList.toggle('show');
      sidebarOverlay?.classList.toggle('show');
    });
  }

  if (sidebarOverlay) {
    sidebarOverlay.addEventListener('click', function() {
      sidebar?.classList.remove('show');
      sidebarOverlay.classList.remove('show');
    });
  }

  window.addEventListener('resize', function() {
    if (window.innerWidth >= 768) {
      sidebar?.classList.remove('show');
      sidebarOverlay?.classList.remove('show');
    }
  });
});