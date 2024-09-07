import flet as ft
import time
import asyncio



# Open directory dialog
def get_directory_result(e: ft.FilePickerResultEvent):
    directory_path.value = e.path if e.path else "Cancelled!"
    directory_path.update()

get_directory_dialog = ft.FilePicker(on_result=get_directory_result)
directory_path = ft.Text()
def set_theme(e,color):
    e.control.page.theme = ft.Theme(color_scheme_seed=color)
    e.control.page.update()
def progress_bar():
    t = ft.Text(value="")
    t2 = ft.Text(value = "0")
    pb = ft.ProgressBar(value=0)
    # img = "https://picsum.photos/200/200?0"
    def button_clicked(e):
        t.value = "Downloading"
        t.update()
        b.disabled = True
        b.update()
        
        for i in range(0, 101):
            # view.content.controls[0].image_src = f"https://picsum.photos/id/{i+10}/200/300"
            # view.content.controls[0].image_opacity = 0.2
            t2.value = i
            pb.value = i * 0.01
            time.sleep(0.1)
            view.update()
            t2.update()
            pb.update()
        t.value = ""
        t2.value = ""
        t.update()
        b.disabled = False
        b.update()
    
    b = ft.ElevatedButton("Download Playlist", width=200000, on_click=button_clicked)
    view = ft.Container(
        
        content = ft.Column(
            [
                b,
                ft.Container(
                    # image_src=img,
                    # image_opacity= 0,
                    # image_fit= ft.ImageFit.COVER,
                    padding=10,
                    content=ft.Column([
                        ft.Divider(opacity=0),
                        t, 
                        pb,
                        t2,
                        ft.Divider(opacity=0)]),
                        
                    )
                
            ],)
    )
    return view
        
   
class GestureDetector:
    def __init__(self):
        self.detector = ft.GestureDetector(
            on_pan_update=self.on_pan_update
        )
    def on_pan_update(self,e):
        if e.delta_x<-20:
            switch_to_sp_tab(e)
        elif e.delta_x>20:
            switch_to_yt_tab(e)
def navigation_drawer():
    def page_launch(e):
        e.control.page.launch_url('https://gallery.flet.dev/icons-browser/')
    def close_end_drawer(e):
        e.control.page.end_drawer = end_drawer
        end_drawer.open = False
        e.control.page.update()
    end_drawer = ft.NavigationDrawer([
        ft.SafeArea(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(""),
                            ft.IconButton(icon=ft.icons.CLOSE,on_click=close_end_drawer)
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    ft.Text("Spotify api key:"),
                    ft.TextField(keyboard_type=ft.KeyboardType.TEXT),
                    ft.TextButton("How To Get Spotify api api Keys",on_click=page_launch)

                ]
            ),
            minimum_padding= 10,
        )
    ])
    
    def open_end_drawer(e):
        e.control.page.end_drawer = end_drawer
        end_drawer.open = True
        e.control.page.update()

    return open_end_drawer
    

def drop_down():
    
    return ft.Dropdown(
            label="Song Exist Action",
            hint_text="What to do when that song already exist in your directory?",
            options=[
                ft.dropdown.Option("Replace all"),
                ft.dropdown.Option("Skip all"),
            ],
            autofocus=True,
        )
def app_bar():
    view = ft.AppBar(
        title=ft.Text("Trackster"),
        actions=[
            ft.IconButton(ft.icons.MENU, style=ft.ButtonStyle(padding=0),on_click=navigation_drawer())
        ],
        bgcolor=ft.colors.with_opacity(0.04, ft.cupertino_colors.SYSTEM_BACKGROUND),
    )
    return view

def handle_nav_change(e):
    if e.control.selected_index == 0:
        switch_to_yt_tab(e)
    elif e.control.selected_index == 1:
        switch_to_sp_tab(e)
def nav_bar():
    view = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.icons.ONDEMAND_VIDEO_ROUNDED, label="Youtube"),
            ft.NavigationBarDestination(icon=ft.icons.MUSIC_NOTE, label="Spotify")
            
        ],
        on_change=handle_nav_change,
        border=ft.Border(
            top=ft.BorderSide(color=ft.cupertino_colors.SYSTEM_GREY2, width=0)
        ),
    )
    return view 


class FolderPicker(ft.Row):
    def build(self):
        view = ft.Row(
                [
                    ft.ElevatedButton(
                        "Select Folder",
                        icon=ft.icons.FOLDER_OPEN,
                        on_click=lambda _: get_directory_dialog.get_directory_path()
                    ),
                    directory_path,
                    # ft.Text(value="Select Output Direcotry to save the playlist", italic=False, selectable=False, style='labelSmall', ),
                ]
            )
        return view
def switch_to_yt_tab(e):
    e.control.page.title= "Youtube"
    set_theme(e,"Red")
    e.control.page.youtube_tab.visible = True
    e.control.page.spotify_tab.visible = False
    e.control.page.navigation_bar.selected_index = 0
    e.control.page.update()

def switch_to_sp_tab(e):
    e.control.page.title= "Spotify"
    set_theme(e,"Green")
    e.control.page.youtube_tab.visible = False
    e.control.page.spotify_tab.visible = True
    e.control.page.navigation_bar.selected_index = 1
    e.control.page.update()

def main(page: ft.Page):
    page.adaptive = True
    page.appbar = app_bar()
    page.navigation_bar = nav_bar()
    # hide all dialogs in overlay
    folder_picker = FolderPicker()
    url = ft.TextField(keyboard_type=ft.KeyboardType.TEXT)
    pb = ft.ProgressBar()
    # def switch_to_yt_tab(e):
    #     page.title= "Youtube"
    #     youtube_tab.visible = True
    #     spotify_tab.visible = False
    #     page.navigation_bar.selected_index = 0
    #     page.update
    
    # def switch_to_sp_tab(e):
    #     page.title= "Spotify"
    #     youtube_tab.visible = False
    #     spotify_tab.visible = True
    #     page.navigation_bar.selected_index = 1
    #     page.update
    page.theme = ft.Theme(color_scheme_seed="Red")   
    gesture_detector = GestureDetector()

    youtube_tab = ft.Container(
        ft.SafeArea(
            content=ft.Column(
                [
                    ft.Divider(opacity=0, height= 20),
                    folder_picker,
                    ft.Divider(opacity=0, height= 20),
                    ft.Text("Enter Youtube playlist url:"),
                    url,
                    ft.Divider(opacity=0),  
                    drop_down(),
                    ft.Divider(opacity=0),
                    # ft.ElevatedButton(text="Download Playlist",width=200000),
                    ft.Divider(opacity=0),
                    progress_bar(),
                    # ft.FilledButton("sp",on_click=switch_to_sp_tab)
                    gesture_detector.detector,

                ]
            )
        ),
        visible= True
    )
    
    spotify_tab = ft.Container(
        ft.SafeArea(
            content=ft.Column(
                [
                    ft.Divider(opacity=0, height= 20),
                    folder_picker,
                    ft.Divider(opacity=0, height= 20),
                    ft.Text("Enter Spotify playlist url:"),
                    url,
                    ft.Divider(opacity=0),  
                    drop_down(),
                    ft.Divider(opacity=0),
                    # ft.ElevatedButton(text="Download Playlist",width=200000),
                    ft.Divider(opacity=0),
                    progress_bar(),
                    # ft.FilledButton("yt",on_click=switch_to_yt_tab)
                    gesture_detector.detector,
                ]
            )
        ),
        visible= False
    )
    page.spotify_tab=spotify_tab
    page.youtube_tab = youtube_tab
    page.overlay.extend([ get_directory_dialog])
    
    page.add(
        youtube_tab,spotify_tab
    )
    for i in range(0, 101):
            pb.value = i * 0.01
            time.sleep(0.1)
            page.update()


ft.app(target=main)