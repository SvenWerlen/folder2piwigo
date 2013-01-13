# folder2piwigo

folder2piwigo is a script written in Python which facilitates the synchronization
between a folder and [Piwigo](http://piwigo.org/).

[Piwigo](http://piwigo.org/) is a famous open-source online photo gallery.
folder2piwigo simplifies the synchronization between your local gallery (Digikam for example) and Piwigo. It provides features like:
* Similar to rsync (only upload new pictures)
* Automatic rescaling of your pictures
* Re-encode videos
* Generate thumbnails for videos
* Ignore some folders
* ...

How does it work?
* You run the script from your machine
* Depending on the selected implementation:
** The script synchronizes your local albums with Piwigo (using FTP)
** The script synchronizes your local albums with Piwigo (using the web API)
* You use the "Admin | Synchronize" tool from Piwigo (only for FTP implementation)
* Your online galleries are updated

For more details, please see:
* [Wiki Home](https://github.com/SvenWerlen/folder2piwigo/wiki)
* [Installation Guide](https://github.com/SvenWerlen/folder2piwigo/wiki/Installation-guide)
* [Frequently Asked Questions](https://github.com/SvenWerlen/folder2piwigo/wiki/Frequently-asked-questions)
