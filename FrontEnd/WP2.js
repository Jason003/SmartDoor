
let apigClient = apigClientFactory.newClient();

var headerParams = {
    //This is where any header, path, or querystring request params go. The key is the parameter named as defined in the API
    "Content-type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "x-api-key": "Your API Key",
    "Access-Control-Allow-Credentials" : "true", 
    "Access-Control-Allow-Methods" : "GET,HEAD,OPTIONS,POST,PUT",
    "Access-Control-Allow-Headers" : "*"
};

let errorDiv = document.getElementById('error-message');
let passewordDiv = document.getElementById("inputPassword");
let sendMessageDiv = document.getElementById("sendButton");

// Setup easy way to reference values of the input password boxes
function passwordValue() { return passewordDiv.value }

// Add listeners for each button that make the API request
sendMessageDiv.addEventListener('click', function(e) {
    errorDiv.textContent = '';
    sendPasswordToApi(e);
});

// Prepare to send data
function sendPasswordToApi(e){
    var oneTimePassword = passwordValue();
    callApi({ "OTP": oneTimePassword });
    var passwordInputBox = document.getElementById("inputPassword");
    passwordInputBox.value = "";
    passwordInputBox.textContent = '';
}

// Send HTTP POST request to AWS Gateway and get the response
function callApi(query) {
    apigClient.validateotpPost(headerParams, query, {})
        .then(function(result) {
            console.log(result);
            let msg = result.data;
            alert(msg);
        })
        .catch(function(err) {
            errorDiv.textContent = 'Failed! There was an error:\n' + err.toString();
        });
}           
