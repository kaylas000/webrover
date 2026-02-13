// Main JavaScript for AI Corporation Web Panel

document.addEventListener(DOMContentLoaded, function() {
    console.log(AI Corporation Web Panel loaded);
    
    // Add any custom JavaScript functionality here
    
    // Example: Auto-refresh status every 30 seconds on status page
    if (window.location.pathname === /status) {
        setInterval(function() {
            fetch(/api/status)
                .then(response => response.json())
                .then(data => {
                    // Update status indicators
                    updateStatusIndicators(data);
                })
                .catch(error => {
                    console.error(Error fetching status:, error);
                });
        }, 30000);
    }
});

function updateStatusIndicators(statusData) {
    // This function would update the status page with fresh data
    // Implementation depends on the specific HTML structure
    console.log(Status updated:, statusData);
}

// Utility function to handle form submissions with AJAX
function submitForm(formId, successCallback, errorCallback) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    form.addEventListener(submit, async function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const action = form.getAttribute(action) || window.location.pathname;
        const method = form.getAttribute(method) || POST;
        
        try {
            const response = await fetch(action, {
                method: method,
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                if (successCallback) successCallback(data);
            } else {
                if (errorCallback) errorCallback(data);
            }
        } catch (error) {
            if (errorCallback) errorCallback({ error: error.message });
        }
    });
}
