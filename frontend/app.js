document.addEventListener('DOMContentLoaded', () => {
    const authSection = document.getElementById('auth-section');
    const employeeSection = document.getElementById('employee-section');
    const loginForm = document.getElementById('login-form');
    const logoutButton = document.getElementById('logout-button');
    const authMessage = document.getElementById('auth-message');
    const loggedInUserSpan = document.getElementById('logged-in-user');
    const employeeListDiv = document.getElementById('employee-list');
    const employeeForm = document.getElementById('employee-form');
    const refreshEmployeesButton = document.getElementById('refresh-employees');
    const employeeMessage = document.getElementById('employee-message');
    const cancelEditButton = document.getElementById('cancel-edit');
    const loadingIndicator = document.getElementById('loading-indicator');
    const photoInput = document.getElementById('photo');
    const photoPreview = document.getElementById('photo-preview');
    const badgesCheckboxesDiv = document.getElementById('badges-checkboxes');

    let jwtToken = localStorage.getItem('jwtToken');

    const API_BASE_URL = ''; // Gateway is serving static files, so relative path works
    const DEFAULT_PHOTO_PLACEHOLDER = '/no_photo.png';

    // --- Utility Functions ---
    function showMessage(element, message, isError = false) {
        element.textContent = message;
        element.style.color = isError ? 'red' : 'green';
        setTimeout(() => {
            element.textContent = '';
        }, 5000);
    }

    function showLoading() {
        loadingIndicator.style.display = 'block';
    }

    function hideLoading() {
        loadingIndicator.style.display = 'none';
    }

    function setAuthUI(loggedIn) {
        if (loggedIn) {
            authSection.style.display = 'none';
            employeeSection.style.display = 'block';
            const payload = JSON.parse(atob(jwtToken.split('.')[1]));
            loggedInUserSpan.textContent = payload.user;
            fetchEmployees();
        } else {
            authSection.style.display = 'block';
            employeeSection.style.display = 'none';
            loggedInUserSpan.textContent = '';
            employeeListDiv.innerHTML = '';
            resetEmployeeForm();
        }
    }

    function getAuthHeaders() {
        if (jwtToken) {
            return {
                'Authorization': `Bearer ${jwtToken}`
            };
        }
        return {};
    }

    function resetEmployeeForm() {
        employeeForm.reset();
        document.getElementById('employee-id').value = '';
        cancelEditButton.style.display = 'none';
        employeeForm.querySelector('button[type="submit"]').textContent = 'Save Employee';
        photoPreview.src = DEFAULT_PHOTO_PLACEHOLDER; // Reset photo preview
        // Uncheck all badges
        badgesCheckboxesDiv.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.checked = false;
        });
    }

    // --- Authentication ---
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        showLoading();
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;

        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (response.ok) {
                jwtToken = data.token;
                localStorage.setItem('jwtToken', jwtToken);
                showMessage(authMessage, 'Login successful!');
                setAuthUI(true);
            } else {
                showMessage(authMessage, data.message || 'Login failed', true);
            }
        } catch (error) {
            showMessage(authMessage, `Error: ${error.message}`, true);
        } finally {
            hideLoading();
        }
    });

    logoutButton.addEventListener('click', () => {
        jwtToken = null;
        localStorage.removeItem('jwtToken');
        showMessage(authMessage, 'Logged out successfully.');
        setAuthUI(false);
    });

    // --- Image Preview ---
    photoInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                photoPreview.src = e.target.result;
            };
            reader.readAsDataURL(file);
        } else {
            photoPreview.src = DEFAULT_PHOTO_PLACEHOLDER;
        }
    });

    // --- Employee Management ---
    async function fetchEmployees() {
        showLoading();
        try {
            const response = await fetch(`${API_BASE_URL}/api/employee/employees`, {
                method: 'GET',
                headers: getAuthHeaders()
            });

            if (response.status === 401) {
                showMessage(employeeMessage, 'Unauthorized. Please log in again.', true);
                logoutButton.click(); // Force logout
                return;
            }

            const employees = await response.json();

            if (response.ok) {
                employeeListDiv.innerHTML = '';
                if (employees.length === 0) {
                    employeeListDiv.innerHTML = '<p>No employees found.</p>';
                    return;
                }
                employees.forEach(emp => {
                    const empDiv = document.createElement('div');
                    empDiv.className = 'employee-item';
                    empDiv.innerHTML = `
                        <img src="${emp.photo_url ? API_BASE_URL + '/static' + emp.photo_url : DEFAULT_PHOTO_PLACEHOLDER}" alt="${emp.full_name}" width="120" height="160">
                        <div>
                            <h4>${emp.full_name} (${emp.job_title})</h4>
                            <p>Location: ${emp.location}</p>
                            <p>Badges: ${emp.badges || 'N/A'}</p>
                            <button class="edit-employee" data-id="${emp.id}">Edit</button>
                            <button class="delete-employee" data-id="${emp.id}">Delete</button>
                        </div>
                    `;
                    employeeListDiv.appendChild(empDiv);
                });
                addEmployeeEventListeners();
            } else {
                showMessage(employeeMessage, employees.message || 'Failed to fetch employees', true);
            }
        } catch (error) {
            showMessage(employeeMessage, `Error fetching employees: ${error.message}`, true);
        } finally {
            hideLoading();
        }
    }

    function addEmployeeEventListeners() {
        document.querySelectorAll('.edit-employee').forEach(button => {
            button.addEventListener('click', async (e) => {
                showLoading();
                const id = e.target.dataset.id;
                try {
                    const response = await fetch(`${API_BASE_URL}/api/employee/employee/${id}`, {
                        method: 'GET',
                        headers: getAuthHeaders()
                    });
                    const employee = await response.json();
                    if (response.ok) {
                        document.getElementById('employee-id').value = employee.id;
                        document.getElementById('full_name').value = employee.full_name;
                        document.getElementById('location').value = employee.location;
                        document.getElementById('job_title').value = employee.job_title;
                        // Set photo preview
                        photoPreview.src = employee.photo_url ? API_BASE_URL + '/static' + employee.photo_url : DEFAULT_PHOTO_PLACEHOLDER;
                        // Set badges checkboxes
                        badgesCheckboxesDiv.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
                            checkbox.checked = employee.badges.includes(checkbox.value);
                        });

                        cancelEditButton.style.display = 'inline-block';
                        employeeForm.querySelector('button[type="submit"]').textContent = 'Update Employee';
                    } else {
                        showMessage(employeeMessage, employee.message || 'Failed to load employee for edit', true);
                    }
                } catch (error) {
                    showMessage(employeeMessage, `Error loading employee: ${error.message}`, true);
                } finally {
                    hideLoading();
                }
            });
        });

        document.querySelectorAll('.delete-employee').forEach(button => {
            button.addEventListener('click', async (e) => {
                const id = e.target.dataset.id;
                if (confirm('Are you sure you want to delete this employee?')) {
                    showLoading();
                    try {
                        const response = await fetch(`${API_BASE_URL}/api/employee/employee/${id}`, {
                            method: 'DELETE',
                            headers: getAuthHeaders()
                        });
                        const data = await response.json();
                        if (response.ok) {
                            showMessage(employeeMessage, data.message || 'Employee deleted successfully.');
                            fetchEmployees();
                        } else {
                            showMessage(employeeMessage, data.message || 'Failed to delete employee', true);
                        }
                    } catch (error) {
                        showMessage(employeeMessage, `Error deleting employee: ${error.message}`, true);
                    } finally {
                        hideLoading();
                    }
                }
            });
        });
    }

    employeeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        showLoading();
        const id = document.getElementById('employee-id').value;
        const full_name = document.getElementById('full_name').value;
        const location = document.getElementById('location').value;
        const job_title = document.getElementById('job_title').value;
        // Get selected badges
        const selectedBadges = Array.from(badgesCheckboxesDiv.querySelectorAll('input[type="checkbox"]:checked'))
                                    .map(cb => cb.value)
                                    .join(',');
        const photo = document.getElementById('photo').files[0];

        const formData = new FormData();
        if (id) formData.append('employee_id', id);
        formData.append('full_name', full_name);
        formData.append('location', location);
        formData.append('job_title', job_title);
        formData.append('badges', selectedBadges); // Use selected badges
        if (photo) formData.append('photo', photo);

        try {
            const response = await fetch(`${API_BASE_URL}/api/employee/employee`, {
                method: 'POST', // POST is used for both create and update with Flask-RESTful pattern
                headers: getAuthHeaders(),
                body: formData
            });

            if (response.status === 401) {
                showMessage(employeeMessage, 'Unauthorized. Please log in again.', true);
                logoutButton.click();
                return;
            }

            const data = await response.json();

            if (response.ok) {
                showMessage(employeeMessage, `Employee ${id ? 'updated' : 'added'} successfully!`);
                resetEmployeeForm();
                fetchEmployees();
            } else {
                showMessage(employeeMessage, data.error || `Failed to ${id ? 'update' : 'add'} employee`, true);
            }
        } catch (error) {
            showMessage(employeeMessage, `Error saving employee: ${error.message}`, true);
        } finally {
            hideLoading();
        }
    });

    refreshEmployeesButton.addEventListener('click', fetchEmployees);
    cancelEditButton.addEventListener('click', resetEmployeeForm);

    // Initial check for token
    if (jwtToken) {
        setAuthUI(true);
    } else {
        setAuthUI(false);
    }
});