window.authFetch = function(url, options={}) {
    const token = localStorage.getItem('vigilacore_token');
    options.headers = options.headers || {};
    if (token) {
        options.headers['Authorization'] = 'Bearer ' + token;
    }
    return fetch(url, options);
}