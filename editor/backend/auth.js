(()=>{
 const $=id=>document.getElementById(id),params=new URLSearchParams(location.hash.slice(1)),invite=params.get('invite');
 // Invitations stay in the URL fragment and are removed before any requests or history navigation.
 if(invite){history.replaceState(null,'','/signin');$('title').textContent='Welcome to your village.';$('intro').textContent='Choose a staff passphrase to accept your invitation. No GitHub account is needed.';$('email').required=false;$('email').hidden=true;$('emailLabel').hidden=true;$('password').autocomplete='new-password';$('submit').textContent='Activate staff access';$('tip').textContent='Use a memorable passphrase with at least 14 characters. This invitation works once and expires after 24 hours.';}
 $('authForm').onsubmit=async e=>{e.preventDefault();$('submit').disabled=true;$('error').textContent='';try{
 const response=await fetch(invite?'/api/auth/enroll':'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(invite?{token:invite,password:$('password').value}:{email:$('email').value,password:$('password').value})});
 const data=await response.json();if(!response.ok)throw Error(data.error||'Sign in could not be completed.');$('password').value='';location.assign('/');
 }catch(error){$('error').textContent=error.message;$('submit').disabled=false;}};
})();
