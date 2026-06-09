# Plastid IR Search
An NCBI-based search engine that compares searches from the NCBI Entrez API with annotated inverted repeats in plant plastid records.

## Description

Organelles are analogous to mini-organs within the cells of multicellular organisms like 
plants, animals, fungi, algae, and just about anything else that is not bacteria or archaea. Some of 
these organelles, such as mitochondria and chloroplasts, are believed to have evolved from 
bacteria that had a symbiotic relationship with an ancient cell lineage. As such, both chloroplasts 
and mitochondria still have their own genomes, or genetic material. These genomes have been 
significantly reduced via billions of years of evolution, but there are completed maps of these 
DNA sequences of organelles for different species in genetic databases.

Plastid IR Search is a search engine for complete *plastid* genome records. Plastids are a type of organelle 
only found in plants, algae, and a few other eukaryotes. Chloroplasts, the organelles responsible for photosynthesis in 
plants, are actually a type of plastid. One of the more unique features of plastid genomes is that 
they mostly consist of what are known as inverted repeats (IRs). Basically, these are two separate sections of the genome that are "opposites" (complements) of each other and, when lined up, match each other's opposing base. For example, IrA (the first inverted repeat) could look like:
```
GCTTATTCTCTATGCGGGG
```
and then IrB would be the same sequence backwards and have its A bases swapped with Ts and Cs swapped with Gs (and vice versa) and it will look like:
```
CCCCGCATAGAGAATAAGC
```
In GenBank, some of these complete plastid genome records do not note, or annotate, whether there is
an inverted repeat present or not. Plastid IR Search tries to locate the presence of these notes in the
records and if they're present, it gives the exact locations according to the notes.

## How to Use

Just like any search engine, make your search by typing whatever plant or alga you want into the
search engine, no registration needed! You can even see a graph of how many *annotated* records were added
throughout time.
<br>
<br>
![PlastidIRHome.png](https://i.ibb.co/2LFCvbj/Plastid-IRHome.png)
<br>
<br>
### About

On the button at the left-hand corner. This button mainly tells you basic information and *some* FAQS
about the project so you don't have to look at the Github page every time you want to do find something
out. Mainly, it has a legend for the symbols in inverted repeats in case you want to know what each one does.
<br>

### Searches

You can search any eukaryotic organism you want on this search engine. Be it rice, a species
of seaweed, or even a potato. For maximum results, I highly suggest you use the scientific family or family of the organism you want to look up.
Be warned though that due to rate-limiting, the results will be slower the more results generated.
<br>
<br>
If you get no results, don't worry: just search again.
<br>
<br>
![PlastidIRResults.png](https://i.ibb.co/rGqjTsM2/Plastid-IRSearch2.png) 
<br>
<br>
Like my previous projects, this program gives you the Accession IDs of each genetic record, title, description, dates of last update and creation along with the base pair length of the DNA sequence in each record.  There is a new column this time: `IR Reported in Record File?` 
<br>
<br>
Unlike my previous projects, the purpose of Plastid IR Search is to tell you information on whether inverted repeats were *annotated* in the actual
genetic records of these plants and algae which is achieved via the analysis of more than 40000 genetic records. From the internal About page, here is the basic legend: 
<br>
<br>
![PlastidIRLegend.png](https://i.ibb.co/r2dy01vw/Plastid-IRLegend.png) 
<br>
<br>
You may have noticed that in the screenshot before the legend, the `Accession` column is hyperlinked. That's because when you click on it, a different output appears depending on what `IR Reported in Record File?` says. If you click on it when there is an X, the program will simply tell you there was nothing found. If you click on a row with a dash however: 
<br>
<br>
![PlastidIRHyperlink.png](https://i.ibb.co/yBF5Rr59/Plastid-IRHyperlink.png) 
<br>
<br>
You can click on the hyperlink and be redirected to the NCBI page and download the .gb (Genbank) file from there. Afterwards, just place it in your `genbank_files` directory and run `python manage.py ir_setup` which is explained more in the installation instructions. If you click on a hyperlink with a check mark, you'll instead get the results of the IR annotations.
<br>
<br>
![PlastidIRFound.png](https://i.ibb.co/TxcQCNvn/Plastid-IRFound.png)
<br>
<br>
When you're done looking at the results, click the logo or
make a new search using the Result search bar. 
<br>

Need some ideas of what to search for? Try these organisms:
 * *Solanum tuberosum* - Potato
 * *Camellia sinensis* - Tea plant
 * *Nicotiana tabacum* - Tobacco
 * *Saccharina japonica* - Kombu seaweed
 * *Taraxacum* - Genus of plants known as dandelions

### History

You may have noticed that at the end of the top black bar, there is an option that
says `History`. As the name suggests, this button lets you view your entire
search history including invalid results. It will also show the time stamp
of when said search was executed. 
<br>
<br>
![PlastidIRHistory.png](https://i.ibb.co/pvJmqmD9/Plastid-IRHistory.png) 
<br>
<br>
If you have a Django admin account, you can also visit the Django admin page to view, delete,
and edit the search histories of users, and view what session key was used. There is a `View Accessions`
button to the right which is explained in the next session.

### View Accessions

This button shows a list of all Accessions associated with that search. Remember how the accessions were hyperlinked? Well here you can find
the same hyperlink for the accessions that will show you if any annotations were found for said accession. The `Download Accessions` button will print out a table that lists whether each Accession had IRs reported in it or not.
<br>
<br>
![PlastidIRHAccessions.png](https://i.ibb.co/spNmZHs6/Plastid-IRAccessions.png)

### Downloads
You can download your history, your search results, AND your accessions found in a search in CSV formats. Every time you try to download, you will always get a confirmation dialogue prompting you to confirm your choice. After confirming, the download will start and you can click out of the box to escape (or hit cancel).

### Admin Page

Completely redone and makes adding Accession Records much easier.
<br>
<br>
![PlastidIRAdmin.png](https://i.ibb.co/q3T69W0W/Plastid-IRAdmin.png)
<br>
<br>
The admin page now allows you to view search history AND manually edit/add Accession records. You can search records by Accession ID, title,
and even time!
<br>
<br>
**NOTE FOR TIME:** Due to the way it is stored in the model, time must be searched in a `dd mm yyyy` format to properly find anything. For example:
```
04 2023
```
This will list records in April of 2023. The spaces are important.
<br>
<br>
![PlastidIRAdminOptions.png](https://i.ibb.co/ns3tPF3n/Plastid-IRAdmin-Options.png)
<br>
<br>
To make things much easier for users, `Yes`,`No`, and making an exception are the only options allowed for inverted repeats. All entries must include
at minimum, an Accession number, an inverted repeat option, and some date for reference. There are additional fields to put in addition information if you select `Yes` but the default is `No` for cleaner fields.
<br>
<br>
![PlastidIRAdminAddRecord.png](https://i.ibb.co/HTtCjZc7/Plastid-IRAdd-Record.png)

## Getting Started

### Installing

This program was made using Python 3.13.11.
 
### Dependencies
 
The requirements.txt file has all the dependencies needed.
The next section will tell you how to install it.
 
### Executing the Program
 
Given the complexity of this program, you will have several steps before you can use it.

#### Download the ZIP under "Releases" and extract the folder.

That folder will represent the root.

#### Step 1: Get your dependencies installed.

* From the directory, get all your dependencies by executing this line on Python:
```
pip install -r requirements.txt
```

#### Step 2: Download the Genbank records (in .7z format), and extract it to the plastid_ir_search folder.

NOT in the `PlastidIRSearch` folder (your root). Put the folder on the same level as `manage.py`, you'll see
why later. As you do so, be sure to also run `cd ./plastid_ir_search` or `cd .\plastid_ir_search` on your terminal (both Windows and Linux).

[Download the needed folder here.](https://drive.google.com/file/d/1D-JlTBUCT_bMl8UBFwnFtCS_qHYZx6ur/view?usp=drive_link)

Fair warning: This folder is around 1.1 GB large and fully decompressed, you're looking at almost 14 GB. It contains over 40000
publicly-available genetic records from [NCBI Genbank.](https://www.ncbi.nlm.nih.gov/genbank/) Don't change the name of the folder.

#### Step 3: Get the models created.

Needed to store important information later on. Just do:

```
python manage.py makemigrations
python manage.py migrate
```

#### Step 4: Execute ir_setup.

This is a custom command that will generate IR values to be associated with each search. It detects that exact `genbank_files` folder on
the manage.py level. This step will take a few minutes since it is computing more than 40000 files. Just do:

```
python manage.py ir_setup
```

OPTIONAL: If you ever want to update your existing files already on tables for any reason, you can do:
```
python manage.py ir_setup -u
```
#### Step 5: Run the server.
Just do:
```
python manage.py runserver
```
After that, the search engine should be up and running and look like the following:

```
Watching for file changes with StatReloader
Performing system checks...

System check identified no issues (0 silenced).
May 01, 2026 - 07:58:08
Django version 6.0.4, using settings 'plastid_ir_search.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```
Visit the address and the page should look like the first screenshot. You have
successfully deployed Plastid IR Search on your own device!

#### OPTIONAL Step 6: Create an admin account.
Just do:
```
python manage.py createsuperuser
```
Put in a username (you can skip the email part) and a password and then head over to http://127.0.0.1:8000/admin/ to
view history and edit exceptions if you so wish.
## Help


* **Why is the program so slow?**

It's because of API limits. Without an API key, the maximum amount of requests you
can make is 3 per second. This has already been accounted for in the script and a limit was placed so 
your connection should be fine.

* **This file does have proper inverted repeats so why is it saying there are none found?**

That's the limit of this program: it only checks if the IRs were manually annotated in the Genbank record, not if the DNA
sequence truly has any inverted repeats or not. It is currently not capable of scanning the entire DNA sequence and finding
out what IRs are present, it just looks at the notes. A good analogy for this is it checks if you put your
name on the assignment, but not if you actually did the assignment itself.


* **Why did these files have to be downloaded and not instead done via the API?**

Once again, API limits. If you go any faster than that 3 request per second threshold, your connection could be arbitrarily closed which has already happened to me a couple of times. The rate limiting already limits searches to take around 10 seconds for 1000 results. If I were to fetch a new file from the API every time a search was executed, that would turn into 10 or more minutes.

* **ERROR: Could not find a version that satisfies the requirement package==version_number**

This has happened to me a couple of times. Usually it means that the Python environment you are using has repositories not yet updated. In fact,
the Biopython I was using during this project is the latest version that came one month ago! Try setting up a .venv to remedy that doing:
```
python -m venv .venv
source .venv/bin/activate
```
or depending on what type of Python you have:
```
python3 -m venv .venv
source .venv/bin/activate
```
Alternatively, you could try taking out the version number and stick with the latest package in your Python repository. I imagine this would most likely work.

## Authors
 
* David Bohorquez
 
## Version History

* Released as PlastidIRSearch.zip.
 
## License
 
This project is licensed under the GNU General Public License - see the LICENSE.md file for details
 
## Acknowledgments

So many I could name but here the most important pages that have helped me for this project.


* [airpg by Michael Gruenstaeudl. He gave me permission to use ir_operations.py in his script for this project.](https://github.com/michaelgruenstaeudl/airpg)
* [NCBI and its contributors for their records.](https://www.ncbi.nlm.nih.gov/genbank/)
* [This public domain flower for the logo and favicon.](https://pdimagearchive.org/images/f2b4aa77-8385-4fa2-9a32-b673e48f8047/) 
* [Magda Ehlers for the background image.](https://www.pexels.com/photo/lush-green-leafy-background-texture-29295558/)
* [Bootstrap Template for Search Bar](https://bootstrapexamples.com/@anonymous/search-bar-with-search-icon-in-bootstrap-5-2)
* [Bootstrap Template for Error Page](https://bootstrapexamples.com/@valeria/404-page-template-2)
* [This favicon tutorial.](https://learndjango.com/tutorials/django-favicon-tutorial)
* [This article helped in creating the ir_setup command.](https://www.geeksforgeeks.org/python/custom-django-management-commands/)
* [Making queries in Django.](https://docs.djangoproject.com/en/5.0/topics/db/queries/#lookups-that-span-relationships)
* [Session usage eliminated the email requirement present in the previous projects.](https://docs.djangoproject.com/en/6.0/topics/http/sessions/)
* [Bootstrap Icons for the symbols.](https://icons.getbootstrap.com/)
* [Plotly documentation.](https://plotly.com/python/plotly-express/)
* [Polars documentation, specifically for transformations.](https://docs.pola.rs/)
* [Modified Heroic Template used for base.html](https://github.com/startbootstrap/startbootstrap-heroic-features)
* [Bootstrap Navbar Documentation](https://getbootstrap.com/docs/4.0/components/navbar/#text)
* [Django-pandas for making CSV exports much easier.](https://django-pandas.readthedocs.io/en/latest/)
* [Django Unfold for making my admin look much nicer.](https://unfoldadmin.com/docs/installation/quickstart/)
* [Biopython for supplying both the Entrez API for searches and SeqIO for the offline file parsing.](https://biopython.org/)
