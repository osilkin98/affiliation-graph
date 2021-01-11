import requests as re
import json
import base64
import time
import networkx as nx
import matplotlib.pyplot as plt
from requests.api import request


# request the API and return the json body 
def request_api(method, **kwargs):
    resp = method(**kwargs)
    body = resp.json()
    
    while 'error' in body:
        # unknown error
        if body['error']['status'] != 429:
            raise Exception(body)
        
        # sleep the amount of time as told by spotify
        retry_after = int(resp.headers['Retry-After'])
        print(f'spotify rate-limiting API, waiting {retry_after} secs')
        try:
            time.sleep(retry_after)
        except TypeError:
            print(f'Response Headers: {resp.headers}')
            print(f'Retry-After: {retry_after}')

        # try again
        resp = method(**kwargs)
        body = resp.json()
    
    return body



# get client-id and client-secret from spotify API 
client_id = ''      
client_secret = ''  
access_token = ''  # access-token is obtained using your client-id & secret

# token save file 
TOKENFILE = 'spotify-token.json'
expired = True



# check if access token is expired
with open(TOKENFILE, 'r') as fp:
    print('reading token from file')
    body = json.load(fp)
    current_time = int(time.time())
    if current_time <= body['expires']:
        expired = False

# todo: have an expired check each time a request runs 
# get an access token from the spotify API
if expired:
    print('token expired, requesting a new one')

    client_encoded = base64.b64encode(str.encode(f'{client_id}:{client_secret}'))
    authorization = 'Basic ' + client_encoded.decode() 
    headers={"Authorization": authorization}
    auth_url = 'https://accounts.spotify.com/api/token'
    data={'grant_type': 'client_credentials'}
    # r = re.post('https://accounts.spotify.com/api/token', data={'grant_type': 'client_credentials'}, headers=headers)

    # save the token 
    body = request_api(re.post, url=auth_url, data=data, headers=headers)
    current_time = int(time.time())
    body['expires'] = current_time + body['expires_in']
    with open(TOKENFILE, 'w') as fp:
        json.dump(body, fp)



access_token = body['access_token']
print(f'Using access token: {access_token}')


url_string = 'https://api.spotify.com/v1'
headers = {
    'Authorization': f'Bearer {access_token}',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

# maps artist IDs to Artist objects 
ARTIST_IDS = {}

# Artist object 
class Artist(object):

    def __init__(self, artist) -> None:
        super().__init__()
        self.id = artist['id']

        # set these in a request
        self.name = artist['name']

    def __repr__(self) -> str:
        return self.name

'''
    # request the spotify API for the artist's specific information
    def _populate_info(self):
        if not self._requested:
            print(f'requesting information for artist id: {self.id}')

            query = f'/artists/{self.id}'
            # req = re.get(url_string + query, headers=headers)
            resp = request_api(re.get, url=url_string+query, headers=headers)
            
            try:
                self.name = resp['name']
                self.images = resp['images']
                self.popularity = resp['popularity']
            except KeyError:
                print(json.dumps(resp, indent=2))
            else:
                # set the requested status 
                self._requested = True
'''



def process_artists(G, artists, artist_ids):
    new_artists = set()  # store all the newly created artists here
    
    # repeat the process for these artist ids 
    for main_artist in artists:

        print(f'=== processing artist {main_artist.name} (id: {main_artist.id}) ===')

        # get 5 artist albums 
        resource = f'/artists/{main_artist.id}/albums'
        payload = {
            'include_groups': ['album'],
            'limit': 5,
        }
        # albums_r = re.get(url_string + resource, headers=headers, params=payload)
        body = request_api(re.get, url=url_string+resource, headers=headers, params=payload)
        albums = body.get('items')

        # extrapolate feature information from each album
        for i, album in enumerate(albums):
            print(f'Processing "{album["name"]}" ({i+1}/{len(albums)})')
            album_id = album['id']
            num_tracks = album['total_tracks']

            # get the album's tracks
            query = f'/albums/{album_id}/tracks'
            payload = {
                'limit': num_tracks
            }
            # tracks_r = re.get(url_string + query, headers=headers, params=payload)
            body = request_api(re.get, url=url_string+query, headers=headers, params=payload)
            tracks = body['items']

            # process the artist information from the tracks
            for j, track in enumerate(tracks):
                # print only one of the responses 

                # count the artist collabs
                for feat_artist in track['artists']:
                    if feat_artist['id'] not in artist_ids:
                        # skip to the next artist in the case of an error
                        try:
                            artist_ids[feat_artist['id']] = Artist(feat_artist)
                        except:
                            continue
                        else:
                            featured_artist = artist_ids[feat_artist['id']]
                            new_artists.add(featured_artist) # add a new artist to be processed 

                    else:
                        featured_artist = artist_ids[feat_artist['id']]

                    # process the featured artist 
                    if featured_artist is not main_artist:
                        # make sure featured artist is in the graph
                        if featured_artist not in G:
                            G.add_node(featured_artist.name)

                        # add a connection between them 
                        if not G.has_edge(featured_artist.name, main_artist.name):
                            G.add_edge(main_artist.name, featured_artist.name, weight=1)
                        else:
                            # increment the weight between them by 1
                            G.edges[main_artist.name, featured_artist.name]['weight'] += 1 
    
    # these are the artists who should be processed next
    return new_artists

# init variables
EXPLORE_DEPTH=1


# find migos in the spotify API
query = input('search artist: ')
resource = '/search'
payload = {
    'q': query,
    'type': 'artist',
    'limit': 1
}

# get the resource
# r = re.get(url_string + resource, headers=headers, params=payload)
body = request_api(re.get, url=url_string + resource, headers=headers, params=payload)

# get the migos id
main_artist = body['artists']['items'].pop()
main_artist = Artist(main_artist)
ARTIST_IDS[main_artist.id] = main_artist


# init features for artist
processed_artists = {}
artists_to_process = {main_artist}

G = nx.Graph()
G.add_node(main_artist.name)


# get all the degrees adjacent to the main artist in the graph
artists_to_process = process_artists(G, artists_to_process, ARTIST_IDS)
process_artists(G, artists_to_process, ARTIST_IDS)


# print out the graph 

# write the graph out 

with open('rapper-graph-adjacency.json', 'w') as outfile:
    print('writing graph data')
    data = nx.adjacency_data(G)
    json.dump(data, outfile, indent=2)

with open('rapper-graph-nodelink.json', 'w') as outfile:
    print('writing graph data')
    data = nx.node_link_data(G)
    json.dump(data, outfile, indent=2)


'''
'''

'''
print('='*50)
print(json.dumps(tracks, indent=2))
print('='*50) 
'''